"""Shared profile eligibility predicates used by API and worker SQL writes."""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased

from trustlens.core.domain.enums import AccountStatus, VerificationStatus
from trustlens.db import models as m


def name_verified(user_id):
    p, identity, seller, user, front, selfie = (
        aliased(c)
        for c in (
            m.AccountProfileModel,
            m.IdentityVerificationModel,
            m.SellerProfile,
            m.User,
            m.IdentityDocumentModel,
            m.IdentityDocumentModel,
        )
    )
    newest = aliased(m.IdentityVerificationModel)
    newer = (
        select(newest.id)
        .where(
            newest.seller_id == seller.id,
            or_(
                newest.created_at > identity.created_at,
                and_(newest.created_at == identity.created_at, newest.id > identity.id),
            ),
        )
        .correlate(seller, identity)
        .exists()
    )
    from trustlens.core.domain.enums import DocumentType

    return (
        select(p.user_id)
        .join(seller, seller.user_id == p.user_id)
        .join(user, user.id == p.user_id)
        .join(identity, identity.id == p.name_identity_id)
        .join(front, front.id == identity.front_document_id)
        .join(selfie, selfie.id == identity.selfie_document_id)
        .where(
            p.user_id == user_id,
            p.name_status == "VERIFIED",
            p.name_verified_at.is_not(None),
            p.public_name.is_not(None),
            identity.seller_id == seller.id,
            identity.decision == VerificationStatus.VERIFIED,
            identity.face_match_engine.in_(["insightface", "deepface"]),
            ~func.coalesce(identity.decision_reason, "").ilike("%DEMO%"),
            front.seller_id == seller.id,
            front.document_type == DocumentType.CNIC_FRONT,
            front.deleted_at.is_(None),
            or_(front.extracted_expiry.is_(None), front.extracted_expiry >= func.current_date()),
            selfie.seller_id == seller.id,
            selfie.document_type == DocumentType.SELFIE,
            selfie.deleted_at.is_(None),
            seller.identity_status == VerificationStatus.VERIFIED,
            seller.deleted_at.is_(None),
            seller.is_flagged.is_(False),
            user.deleted_at.is_(None),
            user.status == AccountStatus.ACTIVE,
            ~newer,
        )
        .correlate_except(p, identity, seller, user, front, selfie)
        .exists()
    )


def profile_ready(user_id):
    p, photo = aliased(m.AccountProfileModel), aliased(m.ProfilePhotoModel)
    return (
        select(p.user_id)
        .join(photo, photo.id == p.approved_photo_id)
        .where(
            p.user_id == user_id,
            p.username_locked.is_(True),
            name_verified(p.user_id),
            photo.user_id == p.user_id,
            photo.status == "APPROVED",
            photo.deleted_at.is_(None),
            photo.identity_id == p.name_identity_id,
            photo.engine.in_(["insightface", "deepface"]),
            photo.threshold >= 0.80,
            photo.similarity >= photo.threshold,
        )
        .correlate_except(p, photo)
        .exists()
    )


def marketplace_profile_ready(user_id):
    """Publication/messaging eligibility; real verification remains separate."""
    from trustlens.db.demo_access import temporary_test_access

    return or_(profile_ready(user_id), temporary_test_access(user_id))


def listing_profile_ready():
    seller = aliased(m.SellerProfile)
    return (
        select(seller.id)
        .where(seller.id == m.ListingModel.seller_id, marketplace_profile_ready(seller.user_id))
        .correlate(m.ListingModel)
        .exists()
    )


def listing_not_paused():
    return (
        ~select(m.ListingPauseModel.listing_id)
        .where(
            m.ListingPauseModel.listing_id == m.ListingModel.id,
            m.ListingPauseModel.paused.is_(True),
        )
        .correlate(m.ListingModel)
        .exists()
    )


async def current_identity(session, seller_id, *, require_media=False, now=None):
    """Use the exact documents of the latest decision, never 'latest by type'."""
    from trustlens.core.domain.enums import DocumentType, FilePurpose
    from trustlens.core.domain.errors import ValidationError

    identity = (
        await session.execute(
            select(m.IdentityVerificationModel)
            .where(m.IdentityVerificationModel.seller_id == seller_id)
            .order_by(
                m.IdentityVerificationModel.created_at.desc(), m.IdentityVerificationModel.id.desc()
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    seller = await session.get(m.SellerProfile, seller_id)
    if (
        not identity
        or not seller
        or seller.identity_status != VerificationStatus.VERIFIED
        or identity.decision != VerificationStatus.VERIFIED
    ):
        raise ValidationError("Complete ID and selfie verification first.", field="identity")
    if (
        identity.face_match_engine not in ("insightface", "deepface")
        or "DEMO" in (identity.decision_reason or "").upper()
        or not identity.front_document_id
        or not identity.selfie_document_id
    ):
        raise ValidationError(
            "This account needs real ID and selfie evidence. Demo checks cannot verify a profile.",
            field="identity",
        )
    front = await session.get(
        m.IdentityDocumentModel, identity.front_document_id, populate_existing=True
    )
    selfie = await session.get(
        m.IdentityDocumentModel, identity.selfie_document_id, populate_existing=True
    )
    if (
        not front
        or not selfie
        or front.seller_id != seller_id
        or selfie.seller_id != seller_id
        or front.document_type != DocumentType.CNIC_FRONT
        or selfie.document_type != DocumentType.SELFIE
        or front.deleted_at
        or selfie.deleted_at
    ):
        raise ValidationError(
            "The verified identity documents are unavailable. Verify your identity again.",
            field="identity",
        )
    if front.extracted_expiry and now and front.extracted_expiry < now.date():
        raise ValidationError(
            "Your identity document has expired. Submit your current ID.", field="identity"
        )
    if require_media:
        for doc, purpose in ((front, FilePurpose.CNIC_FRONT), (selfie, FilePurpose.SELFIE)):
            f = await session.get(m.StoredFileModel, doc.file_id)
            if (
                not f
                or f.owner_user_id != seller.user_id
                or f.purpose != purpose
                or f.deleted_at
                or (f.expires_at and now and f.expires_at <= now)
            ):
                raise ValidationError(
                    "Your private verification photos have expired. Verify your identity again to update your profile.",
                    field="identity",
                )
    return identity, front, selfie
