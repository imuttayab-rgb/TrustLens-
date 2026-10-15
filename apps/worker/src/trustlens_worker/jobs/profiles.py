"""Bounded profile photo check against the exact account's verified selfie."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, text

from trustlens.core.application.services.listing_publication import sync_listing_publication
from trustlens.core.domain.errors import ValidationError
from trustlens.core.domain.policies.profile import photo_result_approved
from trustlens.db import models as m
from trustlens.db.profiles import current_identity

# Conservative initial operating threshold. Requires real-world calibration;
# a retry result is never a fraud verdict or a trust-score penalty.
PROFILE_THRESHOLD = 0.80


async def check_photo(ctx, *, photo_id: str):
    async with ctx["uow"]() as uow:
        # One DP image comparison across worker processes. Small private JPEGs
        # are fetched only after acquiring this lock.
        await uow.session.execute(text("SELECT pg_advisory_xact_lock(847392111)"))
        photo = (
            await uow.session.execute(
                select(m.ProfilePhotoModel)
                .where(m.ProfilePhotoModel.id == UUID(photo_id))
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not photo or photo.deleted_at or photo.status not in ("QUEUED", "PROCESSING", "ERROR"):
            return {"status": photo.status if photo else "MISSING"}
        p = (
            await uow.session.execute(
                select(m.AccountProfileModel)
                .where(m.AccountProfileModel.user_id == photo.user_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        seller = (
            await uow.session.execute(
                select(m.SellerProfile).where(
                    m.SellerProfile.user_id == photo.user_id, m.SellerProfile.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        user = await uow.session.get(m.User, photo.user_id)
        newest = (
            await uow.session.execute(
                select(m.ProfilePhotoModel.id)
                .where(
                    m.ProfilePhotoModel.user_id == photo.user_id,
                    m.ProfilePhotoModel.deleted_at.is_(None),
                )
                .order_by(m.ProfilePhotoModel.created_at.desc(), m.ProfilePhotoModel.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if newest != photo.id or not user or user.deleted_at or not seller or not p:
            photo.status = "SUPERSEDED"
            photo.updated_at = ctx["clock"].now()
            await uow.commit()
            return {"status": photo.status}
        photo.status = "PROCESSING"
        photo.updated_at = ctx["clock"].now()
        await uow.flush()
        try:
            identity, _, selfie = await current_identity(
                uow.session, seller.id, require_media=True, now=ctx["clock"].now()
            )
            if (
                identity.id != photo.identity_id
                or p.name_status != "VERIFIED"
                or p.name_identity_id != identity.id
            ):
                raise ValidationError("Identity changed")
            stored = await uow.session.get(m.StoredFileModel, selfie.file_id)
            compare = getattr(ctx["face"], "compare_profile", None)
            if compare is None:
                photo.status = "ERROR"
                photo.reason = "REAL_FACE_ENGINE_REQUIRED"
            else:
                raw = await ctx["storage"].get(bucket=photo.bucket, object_key=photo.object_key)
                if hashlib.sha256(raw).digest() != photo.sha256:
                    raise ValidationError("Photo changed")
                reference = await ctx["storage"].get(
                    bucket=stored.bucket, object_key=stored.object_key
                )
                if len(reference) > 10 * 1024 * 1024:
                    raise ValidationError("Reference is too large")
                result = await compare(raw, reference, threshold=PROFILE_THRESHOLD)
                photo.engine = result.engine
                photo.similarity = result.similarity
                photo.threshold = result.threshold
                # Re-read the latest verification after CPU work; another
                # request may have replaced or revoked the identity meanwhile.
                await uow.session.refresh(seller)
                fresh, _, _ = await current_identity(uow.session, seller.id, now=ctx["clock"].now())
                if fresh.id != photo.identity_id:
                    raise ValidationError("Identity changed")
                if photo_result_approved(result):
                    photo.status = "APPROVED"
                    photo.reason = None
                    p.approved_photo_id = photo.id
                    p.version += 1
                    await uow.flush()
                    domain_seller = await uow.sellers.get(seller.id)
                    await sync_listing_publication(uow, domain_seller, now=ctx["clock"].now())
                else:
                    photo.status = "RETRY"
                    photo.reason = (
                        "ONE_CLEAR_FACE_REQUIRED"
                        if result.raw.get("reason") == "one_clear_face_required"
                        else "MATCH_INCONCLUSIVE"
                    )
        except ValidationError:
            photo.status = "RETRY"
            photo.reason = "VERIFY_IDENTITY_AGAIN"
        except Exception:
            # Never log image bytes, object URLs, legal names or embeddings.
            photo.status = "ERROR"
            photo.reason = "CHECK_UNAVAILABLE"
        photo.updated_at = ctx["clock"].now()
        await uow.commit()
        return {"status": photo.status, "reason": photo.reason}


async def cleanup_photos(ctx):
    """Old/rejected portraits are private and short-lived; ID retention stays unchanged."""
    async with ctx["uow"]() as uow:
        now = ctx["clock"].now()
        rows = (
            (
                await uow.session.execute(
                    select(m.ProfilePhotoModel)
                    .outerjoin(
                        m.AccountProfileModel,
                        m.AccountProfileModel.approved_photo_id == m.ProfilePhotoModel.id,
                    )
                    .outerjoin(m.User, m.User.id == m.ProfilePhotoModel.user_id)
                    .where(
                        m.ProfilePhotoModel.deleted_at.is_(None),
                        (
                            (m.AccountProfileModel.user_id.is_(None))
                            | m.User.deleted_at.is_not(None)
                        ),
                        m.ProfilePhotoModel.created_at < now - timedelta(days=7),
                    )
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        for photo in rows:
            try:
                await ctx["storage"].delete(bucket=photo.bucket, object_key=photo.object_key)
                photo.deleted_at = now
            except Exception:
                continue
        await uow.commit()
    return {"removed": sum(p.deleted_at is not None for p in rows)}
