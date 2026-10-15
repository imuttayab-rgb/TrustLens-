"""Unified account profile helpers. Full legal names never enter public payloads."""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from trustlens.core.domain.enums import AccountStatus, UserRole, VerificationStatus
from trustlens.core.domain.errors import EntityNotFound, PermissionDenied
from trustlens.core.domain.policies.profile import public_name
from trustlens.db import models as m
from trustlens.db.profiles import marketplace_profile_ready, name_verified, profile_ready
from trustlens.db.demo_access import fixture_label, temporary_test_access

PROFILE_HANDLE_LOCK = 847392109
PHOTO_CONSENT_VERSION = "profile-photo-v1"


async def owner(uow, user_id, *, lock=False):
    query = select(m.User).where(m.User.id == user_id, m.User.deleted_at.is_(None))
    if lock:
        query = query.with_for_update()
    user = (await uow.session.execute(query)).scalar_one_or_none()
    if not user or user.status != AccountStatus.ACTIVE:
        raise PermissionDenied("active_account")
    return user


async def ensure_profile(uow, user_id, container):
    user = await owner(uow, user_id, lock=True)
    seller = (
        await uow.session.execute(select(m.SellerProfile).where(m.SellerProfile.user_id == user_id))
    ).scalar_one_or_none()
    if seller and seller.deleted_at:
        raise PermissionDenied("active_profile")
    if not seller:
        # The random stable initial username reveals no legal name/email.
        handle = f"member-{str(user_id).replace('-', '')}"
        seller = m.SellerProfile(
            id=container.ids.new(),
            user_id=user_id,
            handle=handle,
            display_name="Member",
            country_code="PK",
            account_opened_at=user.created_at,
            email_status=VerificationStatus.VERIFIED
            if user.email_verified_at
            else VerificationStatus.PENDING,
        )
        uow.session.add(seller)
        await uow.session.flush()
    await uow.session.execute(
        insert(m.AccountProfileModel).values(user_id=user_id).on_conflict_do_nothing()
    )
    await uow.session.execute(
        insert(m.ProfileHandleAliasModel)
        .values(handle=seller.handle, user_id=user_id)
        .on_conflict_do_nothing()
    )
    domain = await uow.users.get(user_id)
    added_role = UserRole.SELLER not in domain.roles
    if added_role:
        await uow.users.assign_role(user_id, UserRole.SELLER.value, granted_by=None)
    await uow.commit()
    if added_role:
        await container.cache.incr(f"perm_version:{user_id}")
    return seller


async def resolve_profile(uow, reference):
    query = (
        select(m.SellerProfile)
        .join(m.User, m.User.id == m.SellerProfile.user_id)
        .where(
            m.SellerProfile.deleted_at.is_(None),
            m.User.deleted_at.is_(None),
            m.User.status == AccountStatus.ACTIVE,
        )
    )
    try:
        uid = UUID(reference)
        query = query.where(m.SellerProfile.user_id == uid)
    except ValueError:
        alias = await uow.session.get(m.ProfileHandleAliasModel, reference.lower())
        query = (
            query.where(m.SellerProfile.user_id == alias.user_id)
            if alias
            else query.where(m.SellerProfile.handle == reference)
        )
    seller = (await uow.session.execute(query)).scalar_one_or_none()
    if not seller:
        # Legacy buyers may not have opened the dashboard yet. A stable user
        # URL must still work from an old chat without a mutating public GET.
        try:
            user = await uow.session.get(m.User, UUID(reference))
        except ValueError:
            user = None
        if user and not user.deleted_at and user.status == AccountStatus.ACTIVE:
            return user, None
        raise EntityNotFound("profile", reference)
    return await uow.session.get(m.User, seller.user_id), seller


async def profile_payload(uow, container, user, seller, *, private=False):
    p = await uow.session.get(m.AccountProfileModel, user.id)
    ready = bool((await uow.session.execute(select(profile_ready(user.id)))).scalar_one())
    temporary = (
        False
        if ready
        else bool((await uow.session.execute(select(temporary_test_access(user.id)))).scalar_one())
    )
    latest = None
    if seller:
        latest = (
            await uow.session.execute(
                select(m.IdentityVerificationModel)
                .where(m.IdentityVerificationModel.seller_id == seller.id)
                .order_by(
                    m.IdentityVerificationModel.created_at.desc(),
                    m.IdentityVerificationModel.id.desc(),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
    name_ok = bool((await uow.session.execute(select(name_verified(user.id)))).scalar_one())
    handle = seller.handle if seller and (private or (p and p.username_locked)) else str(user.id)
    profile_ref = seller.handle if seller and p and p.username_locked else str(user.id)
    score = await uow.trust_scores.get_current(seller.id) if seller else None
    photo = (
        await uow.session.get(m.ProfilePhotoModel, p.approved_photo_id)
        if p and p.approved_photo_id
        else None
    )
    matched = bool(ready and photo and not photo.deleted_at)
    data = dict(
        usernameLocked=bool(p and p.username_locked),
        initialized=bool(p and seller),
        userId=str(user.id),
        sellerId=str(seller.id) if seller else None,
        handle=handle,
        profileUrl=f"/profile/{profile_ref}",
        displayName=p.public_name
        if name_ok
        else (fixture_label(user.id) if temporary else "Member"),
        city=seller.city if seller else None,
        countryCode=seller.country_code if seller else "PK",
        bio=seller.bio if seller else None,
        memberSince=user.created_at.isoformat(),
        nameVerified=name_ok,
        photoMatched=matched,
        photoUrl=f"/api/v1/public/profiles/{user.id}/photo?v={photo.id}" if matched else None,
        canInteract=ready or temporary,
        temporaryTestAccess=temporary,
        score=int(score.score) if score else None,
        riskLevel=score.risk_level.value if score else None,
        verification={
            "identity": bool(name_ok),
            "phone": bool(seller and seller.phone_status == VerificationStatus.VERIFIED),
            "email": bool(user.email_verified_at),
        },
    )
    if private:
        pending = (
            await uow.session.execute(
                select(m.ProfilePhotoModel)
                .where(
                    m.ProfilePhotoModel.user_id == user.id, m.ProfilePhotoModel.deleted_at.is_(None)
                )
                .order_by(m.ProfilePhotoModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        request = (
            await uow.session.execute(
                select(m.ProfileNameRequestModel)
                .where(m.ProfileNameRequestModel.user_id == user.id)
                .order_by(m.ProfileNameRequestModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        phone = (
            await uow.session.execute(
                select(m.PhoneNumberModel.e164)
                .where(
                    m.PhoneNumberModel.user_id == user.id,
                    m.PhoneNumberModel.deleted_at.is_(None),
                    m.PhoneNumberModel.is_primary.is_(True),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        front = (
            await uow.session.get(m.IdentityDocumentModel, latest.front_document_id)
            if latest and latest.front_document_id
            else None
        )
        legal = (
            container.encryptor.decrypt(p.name_encrypted.decode())
            if p and p.name_encrypted
            else None
        )
        data.update(
            email=user.email,
            phone=phone,
            nameStatus="VERIFIED"
            if name_ok
            else (
                "REVIEW"
                if request
                and request.status == "REVIEW"
                and latest
                and request.identity_id == latest.id
                else "NOT_STARTED"
            ),
            legalName=legal,
            extractedName=front.extracted_name
            if front and front.ocr_engine not in ("fake", None)
            else None,
            identityStatus=seller.identity_status.value if seller else "NOT_STARTED",
            photoStatus=(
                "ERROR"
                if pending
                and pending.status in ("QUEUED", "PROCESSING")
                and pending.created_at < container.clock.now() - timedelta(minutes=15)
                else pending.status
            )
            if pending
            else "NOT_STARTED",
            photoReason=(
                "CHECK_TIMEOUT"
                if pending
                and pending.status in ("QUEUED", "PROCESSING")
                and pending.created_at < container.clock.now() - timedelta(minutes=15)
                else pending.reason
            )
            if pending
            else None,
            photoRequestId=str(pending.id) if pending else None,
            nameRequestStatus=request.status if request else None,
            nameRequestNote=request.decision_note if request else None,
            version=p.version if p else 1,
        )
    return data


async def require_profile(uow, user_id):
    await owner(uow, user_id)
    if not bool(
        (await uow.session.execute(select(marketplace_profile_ready(user_id)))).scalar_one()
    ):
        from trustlens.core.domain.errors import ValidationError

        raise ValidationError(
            "Confirm your permanent username, ID-matched name and approved profile photo in My Profile before posting publicly or sending messages.",
            field="profile",
        )


def prepare_avatar(raw):
    from PIL import Image, ImageOps

    if not raw or len(raw) > 5 * 1024 * 1024:
        raise ValueError("Use a photo of 5 MB or smaller.")
    with Image.open(BytesIO(raw)) as opened:
        if opened.format not in {"JPEG", "PNG", "WEBP"} or getattr(opened, "n_frames", 1) != 1:
            raise ValueError("Use a still JPEG, PNG or WebP photo.")
        if opened.width * opened.height > 16_000_000 or min(opened.size) < 160:
            raise ValueError(
                "Use a clear photo at least 160px wide and no larger than 16 megapixels."
            )
        opened.draft("RGB", (1000, 1000))
        img = ImageOps.exif_transpose(opened).convert("RGB")
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        output = BytesIO()
        img.save(output, format="JPEG", quality=90)
        return output.getvalue()


async def approve_name(uow, container, p, seller, identity, full_name):
    from sqlalchemy import update

    p.name_status = "VERIFIED"
    p.name_identity_id = identity.id
    p.name_encrypted = container.encryptor.encrypt(full_name).encode()
    p.name_verified_at = container.clock.now()
    p.public_name = public_name(full_name)
    p.version += 1
    seller.display_name = p.public_name
    # User.full_name remains private; counterpart responses use public_name.
    await uow.session.execute(
        update(m.User).where(m.User.id == p.user_id).values(full_name=full_name)
    )
    await uow.session.flush()
