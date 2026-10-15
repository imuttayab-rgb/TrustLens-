"""One owner/public profile; name and portrait are server-verified evidence."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import Field
from sqlalchemy import and_, func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from trustlens.core.domain.enums import ListingStatus, VerificationStatus
from trustlens.core.domain.errors import (
    ConflictError,
    EntityNotFound,
    PermissionDenied,
    RateLimitExceeded,
    ValidationError,
)
from trustlens.core.domain.policies import (
    MAX_HANDLE_LENGTH,
    MIN_HANDLE_LENGTH,
    is_reserved,
    slugify_handle,
)
from trustlens.core.domain.policies.profile import can_confirm_name, clean_name
from trustlens.db import models as m
from trustlens.db.photo_guard import photos_cleared
from trustlens.db.profiles import (
    current_identity,
    listing_not_paused,
    listing_profile_ready,
    profile_ready,
)
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep, require_permissions
from trustlens_api.api.v1.routers.public_scores import _throttle
from trustlens_api.api.v1.schemas.common import Schema, envelope
from trustlens_api.modules.profiles.service import (
    PHOTO_CONSENT_VERSION,
    PROFILE_HANDLE_LOCK,
    approve_name,
    ensure_profile,
    owner,
    prepare_avatar,
    profile_payload,
    require_profile,
    resolve_profile,
)

router = APIRouter(tags=["Profiles"])


class ProfileEdit(Schema):
    confirm_username: bool = False
    handle: str = Field(min_length=3, max_length=64)
    city: str | None = Field(default=None, max_length=80)
    bio: str | None = Field(default=None, max_length=1000)
    version: int = Field(ge=1)


class NameConfirmation(Schema):
    full_name: str = Field(min_length=2, max_length=150)
    public_name_consent: Literal[True]
    request_review: bool = False
    note: str = Field(default="", max_length=1000)


class NameDecision(Schema):
    approve: bool
    note: str = Field(min_length=10, max_length=1000)


class AdAction(Schema):
    action: Literal["pause", "resume", "renew", "sold"]


@router.post("/me/profile/initialize")
async def initialize_profile(actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep):
    seller = await ensure_profile(uow, actor.user_id, container)
    user = await owner(uow, actor.user_id)
    return envelope(
        await profile_payload(uow, container, user, seller, private=True),
        request_id=meta.request_id,
    )


@router.get("/me/profile")
async def get_my_profile(
    actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep, response: Response
):
    response.headers["Cache-Control"] = "no-store"
    user = await owner(uow, actor.user_id)
    seller = (
        await uow.session.execute(
            select(m.SellerProfile).where(
                m.SellerProfile.user_id == user.id, m.SellerProfile.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    return envelope(
        await profile_payload(uow, container, user, seller, private=True),
        request_id=meta.request_id,
    )


@router.patch("/me/profile")
async def edit_profile(
    body: ProfileEdit, actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep
):
    user = await owner(uow, actor.user_id, lock=True)
    await uow.session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": PROFILE_HANDLE_LOCK}
    )
    p = await uow.session.get(m.AccountProfileModel, user.id, with_for_update=True)
    seller = (
        await uow.session.execute(
            select(m.SellerProfile).where(
                m.SellerProfile.user_id == user.id, m.SellerProfile.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not p or not seller:
        raise ConflictError("Open My Profile to finish account setup first.")
    if p.version != body.version:
        raise ConflictError("Your profile changed in another tab. Refresh and try again.")
    handle = body.handle.strip().lower()
    if p.username_locked and handle != str(seller.handle).lower():
        raise ValidationError("Your username is permanent and cannot be changed.", field="handle")
    if not p.username_locked and not body.confirm_username:
        raise ValidationError(
            "Confirm your permanent username. You can choose it only once.", field="confirmUsername"
        )
    if (
        handle != slugify_handle(handle)
        or not MIN_HANDLE_LENGTH <= len(handle) <= MAX_HANDLE_LENGTH
        or is_reserved(handle)
    ):
        raise ValidationError(
            "Choose a unique username using letters, numbers and hyphens. Reserved names are not allowed.",
            field="handle",
        )
    alias = await uow.session.get(m.ProfileHandleAliasModel, handle)
    occupied = (
        await uow.session.execute(
            select(m.SellerProfile.user_id).where(
                m.SellerProfile.handle == handle, m.SellerProfile.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if (alias and alias.user_id != user.id) or (occupied and occupied != user.id):
        raise ConflictError("That username is already taken, including a previous profile link.")
    for value in {str(seller.handle).lower(), handle}:
        await uow.session.execute(
            insert(m.ProfileHandleAliasModel)
            .values(handle=value, user_id=user.id)
            .on_conflict_do_nothing()
        )
    p.username_locked = True
    old_handle = seller.handle
    seller.handle = handle
    seller.city = (body.city or "").strip() or None
    seller.bio = (body.bio or "").strip() or None
    seller.updated_at = container.clock.now()
    p.version += 1
    await uow.commit()
    for key in (
        f"seller:{seller.id}:summary",
        f"score:ref:{old_handle}",
        f"score:ref:{handle}",
    ):
        await container.cache.delete(key)
    return envelope(
        await profile_payload(uow, container, user, seller, private=True),
        request_id=meta.request_id,
    )


@router.post("/me/profile/name")
async def confirm_name(
    body: NameConfirmation, actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep
):
    user = await owner(uow, actor.user_id, lock=True)
    p = await uow.session.get(m.AccountProfileModel, user.id, with_for_update=True)
    seller = (
        await uow.session.execute(
            select(m.SellerProfile).where(
                m.SellerProfile.user_id == user.id, m.SellerProfile.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not p or not seller:
        raise ConflictError("Open My Profile first.")
    identity, front, _ = await current_identity(
        uow.session, seller.id, require_media=True, now=container.clock.now()
    )
    try:
        name = clean_name(body.full_name)
    except ValueError as exc:
        raise ValidationError(str(exc), field="fullName") from exc
    if p.name_status == "VERIFIED" and not body.request_review:
        raise ConflictError("Your verified name is locked. Submit a correction for staff review.")
    can_auto = can_confirm_name(
        name,
        front.extracted_name,
        engine=front.ocr_engine,
        confidence=float(front.ocr_confidence) if front.ocr_confidence is not None else None,
    )
    if can_auto and not body.request_review:
        await approve_name(uow, container, p, seller, identity, name)
        await uow.session.execute(
            update(m.ProfileNameRequestModel)
            .where(
                m.ProfileNameRequestModel.user_id == user.id,
                m.ProfileNameRequestModel.status == "REVIEW",
            )
            .values(status="SUPERSEDED")
        )
        await uow.commit()
        await container.cache.delete(f"seller:{seller.id}:summary")
    else:
        existing = (
            await uow.session.execute(
                select(m.ProfileNameRequestModel.id).where(
                    m.ProfileNameRequestModel.user_id == user.id,
                    m.ProfileNameRequestModel.status == "REVIEW",
                    m.ProfileNameRequestModel.identity_id == identity.id,
                )
            )
        ).first()
        if existing:
            raise ConflictError("Your name is already awaiting staff review.")
        uow.session.add(
            m.ProfileNameRequestModel(
                id=container.ids.new(),
                user_id=user.id,
                identity_id=identity.id,
                requested_encrypted=container.encryptor.encrypt(name).encode(),
                note=body.note.strip(),
                status="REVIEW",
            )
        )
        if not (p.name_status == "VERIFIED" and p.name_identity_id == identity.id):
            p.name_status = "REVIEW"
        p.version += 1
        await uow.commit()
    return envelope(
        await profile_payload(uow, container, user, seller, private=True),
        request_id=meta.request_id,
    )


@router.post("/me/profile/photo", status_code=202)
async def upload_profile_photo(
    request: Request, actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep
):
    # Raw body streaming bounds memory BEFORE image decoding; no multipart
    # parser can spool an unbounded attacker upload first.
    if request.headers.get("x-photo-consent") != PHOTO_CONSENT_VERSION:
        raise ValidationError(
            "Agree to the private photo comparison and public display of your approved photo.",
            field="consent",
        )
    await owner(uow, actor.user_id, lock=True)
    p = await uow.session.get(m.AccountProfileModel, actor.user_id, with_for_update=True)
    seller = (
        await uow.session.execute(
            select(m.SellerProfile).where(
                m.SellerProfile.user_id == actor.user_id, m.SellerProfile.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not p or not seller:
        raise ConflictError("Open My Profile first.")
    now = container.clock.now()
    identity, _, _ = await current_identity(uow.session, seller.id, require_media=True, now=now)
    if p.name_status != "VERIFIED" or p.name_identity_id != identity.id:
        raise ValidationError(
            "Confirm your ID-matched name before uploading your profile photo.", field="name"
        )
    recent = (
        await uow.session.execute(
            select(m.ProfilePhotoModel)
            .where(m.ProfilePhotoModel.user_id == actor.user_id)
            .order_by(m.ProfilePhotoModel.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if recent and recent.created_at > now - timedelta(seconds=60):
        raise RateLimitExceeded(
            "Please wait a minute before uploading another profile photo.", retry_after=60
        )
    if (
        recent
        and recent.status in ("QUEUED", "PROCESSING")
        and recent.created_at > now - timedelta(minutes=15)
    ):
        raise ConflictError("Your photo is still being checked. Please wait for the result.")
    count = (
        await uow.session.execute(
            select(func.count())
            .select_from(m.ProfilePhotoModel)
            .where(
                m.ProfilePhotoModel.user_id == actor.user_id,
                m.ProfilePhotoModel.created_at > now - timedelta(days=1),
            )
        )
    ).scalar_one()
    if count >= 10:
        raise RateLimitExceeded(
            "Daily photo-check limit reached. Try again tomorrow.", retry_after=3600
        )
    acquired = (
        await uow.session.execute(text("SELECT pg_try_advisory_xact_lock(847392110)"))
    ).scalar_one()
    if not acquired:
        raise RateLimitExceeded(
            "Another photo upload is being prepared. Retry shortly.", retry_after=5
        )
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 5 * 1024 * 1024:
            raise ValidationError("Use a photo of 5 MB or smaller.", field="photo")
        raw.extend(chunk)
    try:
        jpeg = await asyncio.to_thread(prepare_avatar, bytes(raw))
    except Exception as exc:
        raise ValidationError(
            "Use a clear still JPEG, PNG or WebP photo, 160px or larger, up to 5 MB / 16 megapixels.",
            field="photo",
        ) from exc
    photo_id = container.ids.new()
    key = f"profile-private/{actor.user_id}/{photo_id}.jpg"
    bucket = container.settings.storage.storage_bucket_documents
    await container.storage.put(
        bucket=bucket,
        object_key=key,
        data=jpeg,
        content_type="image/jpeg",
        server_side_encryption=False,
    )
    photo = m.ProfilePhotoModel(
        id=photo_id,
        user_id=actor.user_id,
        identity_id=identity.id,
        bucket=bucket,
        object_key=key,
        sha256=hashlib.sha256(jpeg).digest(),
        status="QUEUED",
        consent_version=PHOTO_CONSENT_VERSION,
        created_at=now,
        updated_at=now,
    )
    uow.session.add(photo)
    try:
        await uow.commit()
    except Exception:
        await container.storage.delete(bucket=bucket, object_key=key)
        raise
    try:
        await container.queue.enqueue("profiles.check_photo", photo_id=str(photo_id))
    except Exception:
        photo.status = "ERROR"
        photo.reason = "QUEUE_UNAVAILABLE"
        await uow.commit()
        raise ConflictError(
            "Photo saved privately, but checking could not start. Please retry shortly."
        ) from None
    return envelope(
        {"photoRequestId": str(photo_id), "status": "QUEUED"}, request_id=meta.request_id
    )


@router.get("/public/profiles/{reference}")
async def get_public_profile(
    reference: str, container: ContainerDep, uow: UowDep, meta: MetaDep, response: Response
):
    await _throttle(container, meta)
    response.headers["Cache-Control"] = "no-store"
    user, seller = await resolve_profile(uow, reference)
    return envelope(await profile_payload(uow, container, user, seller), request_id=meta.request_id)


@router.get("/public/profiles/{user_id}/photo")
async def public_photo(user_id: UUID, container: ContainerDep, uow: UowDep, meta: MetaDep):
    await _throttle(container, meta)
    ready = bool((await uow.session.execute(select(profile_ready(user_id)))).scalar_one())
    p = await uow.session.get(m.AccountProfileModel, user_id)
    photo = (
        await uow.session.get(m.ProfilePhotoModel, p.approved_photo_id)
        if ready and p and p.approved_photo_id
        else None
    )
    if not photo or photo.deleted_at:
        raise EntityNotFound("profile_photo", user_id)
    raw = await container.storage.get(bucket=photo.bucket, object_key=photo.object_key)
    if hashlib.sha256(raw).digest() != photo.sha256:
        raise EntityNotFound("profile_photo", user_id)
    return Response(
        raw,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/me/profile/ads")
async def owner_ads(
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    tab: Literal["all", "active", "inactive"] = "all",
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=12, ge=1, le=30),
    offset: int = Query(default=0, ge=0),
):
    await owner(uow, actor.user_id)
    seller = (
        await uow.session.execute(
            select(m.SellerProfile).where(
                m.SellerProfile.user_id == actor.user_id, m.SellerProfile.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not seller:
        return envelope(
            {"items": [], "total": 0, "counts": {"all": 0, "active": 0, "inactive": 0}},
            request_id=meta.request_id,
        )
    visible = and_(
        m.ListingModel.status == ListingStatus.ACTIVE,
        listing_profile_ready(),
        listing_not_paused(),
        photos_cleared(),
        seller.phone_status == VerificationStatus.VERIFIED,
        seller.email_status == VerificationStatus.VERIFIED,
    )
    base = select(m.ListingModel).where(
        m.ListingModel.seller_id == seller.id, m.ListingModel.deleted_at.is_(None)
    )
    counts = (
        await uow.session.execute(
            select(func.count(), func.count().filter(visible))
            .select_from(m.ListingModel)
            .where(m.ListingModel.seller_id == seller.id, m.ListingModel.deleted_at.is_(None))
        )
    ).one()
    if q.strip():
        base = base.where(
            m.ListingModel.title.ilike(
                "%" + q.strip().replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"
            )
        )
    if tab == "active":
        base = base.where(visible)
    if tab == "inactive":
        base = base.where(~visible)
    total = (
        await uow.session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        await uow.session.execute(
            base.add_columns(visible)
            .order_by(m.ListingModel.created_at.desc(), m.ListingModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    ids = [r[0].id for r in rows]
    paused = (
        set(
            (
                await uow.session.execute(
                    select(m.ListingPauseModel.listing_id).where(
                        m.ListingPauseModel.listing_id.in_(ids),
                        m.ListingPauseModel.paused.is_(True),
                    )
                )
            ).scalars()
        )
        if ids
        else set()
    )
    from trustlens.db.repositories import _primary_image_ids
    from trustlens_api.api.v1.routers._public_listing_presentation import image_url, thumbnail_url

    images = await _primary_image_ids(uow.session, ids)
    items = []
    for row, is_public in rows:
        img = images.get(row.id)
        url = None
        if img:
            url = await thumbnail_url(container, uow, img[0], img[1]) or await image_url(
                container, uow, img[0]
            )
        shown = (
            "PAUSED"
            if row.id in paused
            else (
                "PROFILE_REQUIRED"
                if row.status == ListingStatus.ACTIVE and not is_public
                else row.status.value
            )
        )
        items.append(
            dict(
                id=str(row.id),
                title=row.title,
                price=float(row.price) if row.price is not None else None,
                currency=row.currency,
                city=row.city,
                status=shown,
                rawStatus=row.status.value,
                isPublic=bool(is_public),
                imageUrl=url,
                createdAt=row.created_at.isoformat(),
            )
        )
    return envelope(
        {
            "items": items,
            "total": total,
            "counts": {"all": counts[0], "active": counts[1], "inactive": counts[0] - counts[1]},
        },
        request_id=meta.request_id,
    )


@router.post("/me/profile/ads/{listing_id}/action")
async def ad_action(
    listing_id: UUID,
    body: AdAction,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
):
    await owner(uow, actor.user_id)
    row = (
        await uow.session.execute(
            select(m.ListingModel)
            .join(m.SellerProfile, m.SellerProfile.id == m.ListingModel.seller_id)
            .where(
                m.ListingModel.id == listing_id,
                m.SellerProfile.user_id == actor.user_id,
                m.ListingModel.deleted_at.is_(None),
            )
            .with_for_update(of=m.ListingModel)
        )
    ).scalar_one_or_none()
    if not row:
        raise EntityNotFound("listing", listing_id)
    from trustlens.core.domain.enums import AuctionStatus

    auction = (
        await uow.session.execute(
            select(m.AuctionModel.id).where(
                m.AuctionModel.listing_id == row.id, m.AuctionModel.status == AuctionStatus.ACTIVE
            )
        )
    ).first()
    if auction:
        raise ConflictError(
            "This ad has an active auction. Manage the auction before changing the ad status."
        )
    if body.action == "pause":
        if row.status not in (ListingStatus.ACTIVE, ListingStatus.DRAFT):
            raise ConflictError("Only active ads or drafts can be paused.")
        await uow.session.execute(
            insert(m.ListingPauseModel)
            .values(listing_id=row.id, paused=True)
            .on_conflict_do_update(index_elements=["listing_id"], set_={"paused": True})
        )
        row.status = ListingStatus.DRAFT
    elif body.action == "sold":
        if row.status != ListingStatus.ACTIVE:
            raise ConflictError(
                "Only an active ad can be marked sold. Complete any reserved deal through its transaction."
            )
        row.status = ListingStatus.SOLD
    else:
        await require_profile(uow, actor.user_id)
        pause = await uow.session.get(m.ListingPauseModel, row.id)
        if body.action == "resume" and not (pause and pause.paused):
            raise ConflictError("This ad is not paused.")
        if body.action == "renew" and row.status != ListingStatus.EXPIRED:
            raise ConflictError("Only expired ads can be renewed.")
        if pause:
            pause.paused = False
        row.status = ListingStatus.DRAFT
    row.version += 1
    row.updated_at = container.clock.now()
    await uow.commit()
    if body.action in ("resume", "renew"):
        from trustlens.core.application.use_cases.listings import RequestListingAnalysis

        await RequestListingAnalysis(uow=uow, queue=container.queue).execute(
            listing_id=row.id, seller_id=row.seller_id
        )
    return envelope({"status": row.status.value}, request_id=meta.request_id)


@router.get(
    "/admin/profile-name-reviews",
    dependencies=[Depends(require_permissions("identity:read:any", "review_case:decide"))],
)
async def name_reviews(
    actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep, response: Response
):
    response.headers["Cache-Control"] = "no-store"
    requests = (
        (
            await uow.session.execute(
                select(m.ProfileNameRequestModel)
                .where(m.ProfileNameRequestModel.status == "REVIEW")
                .order_by(m.ProfileNameRequestModel.created_at)
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    result = []
    for r in requests:
        identity = await uow.session.get(m.IdentityVerificationModel, r.identity_id)
        front = (
            await uow.session.get(m.IdentityDocumentModel, identity.front_document_id)
            if identity and identity.front_document_id
            else None
        )
        stored = await uow.session.get(m.StoredFileModel, front.file_id) if front else None
        preview = None
        if (
            stored
            and stored.owner_user_id == r.user_id
            and not stored.deleted_at
            and (not stored.expires_at or stored.expires_at > container.clock.now())
        ):
            preview = await container.storage.presign_download(
                bucket=stored.bucket, object_key=stored.object_key, ttl_seconds=180
            )
        result.append(
            {
                "id": str(r.id),
                "userId": str(r.user_id),
                "requestedName": container.encryptor.decrypt(r.requested_encrypted.decode()),
                "extractedName": front.extracted_name if front else None,
                "ocrEngine": front.ocr_engine if front else None,
                "note": r.note,
                "documentUrl": preview,
                "createdAt": r.created_at.isoformat(),
            }
        )
    return envelope(result, request_id=meta.request_id)


@router.post(
    "/admin/profile-name-reviews/{review_id}",
    dependencies=[Depends(require_permissions("identity:read:any", "review_case:decide"))],
)
async def decide_name(
    review_id: UUID,
    body: NameDecision,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
):
    r = (
        await uow.session.execute(
            select(m.ProfileNameRequestModel)
            .where(m.ProfileNameRequestModel.id == review_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not r:
        raise EntityNotFound("name_review", review_id)
    if r.status != "REVIEW":
        raise ConflictError("This review was already decided.")
    if r.user_id == actor.user_id:
        raise PermissionDenied("independent_reviewer")
    await owner(uow, r.user_id, lock=True)
    seller = (
        await uow.session.execute(
            select(m.SellerProfile).where(
                m.SellerProfile.user_id == r.user_id, m.SellerProfile.deleted_at.is_(None)
            )
        )
    ).scalar_one()
    p = await uow.session.get(m.AccountProfileModel, r.user_id, with_for_update=True)
    if body.approve:
        identity, _, _ = await current_identity(
            uow.session, seller.id, require_media=True, now=container.clock.now()
        )
        if identity.id != r.identity_id:
            raise ConflictError(
                "The identity changed. Ask the user to submit a new name confirmation."
            )
        name = container.encryptor.decrypt(r.requested_encrypted.decode())
        await approve_name(uow, container, p, seller, identity, name)
    elif p.name_status == "REVIEW":
        p.name_status = "NOT_STARTED"
        p.version += 1
    r.status = "APPROVED" if body.approve else "REJECTED"
    r.decided_by = actor.user_id
    r.decision_note = body.note.strip()
    r.updated_at = container.clock.now()
    from trustlens.core.domain.entities import AuditLogEntry

    # No legal name/document URL is written into audit JSON.
    await uow.audit_logs.record(
        AuditLogEntry(
            id=container.ids.new(),
            actor_id=actor.user_id,
            action="profile.name.decide",
            entity_type="profile_name_request",
            entity_id=r.id,
            occurred_at=container.clock.now(),
            after={"decision": r.status},
        )
    )
    await uow.commit()
    await container.cache.delete(f"seller:{seller.id}:summary")
    return envelope({"status": r.status}, request_id=meta.request_id)
