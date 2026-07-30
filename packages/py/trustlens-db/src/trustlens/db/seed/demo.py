"""Demo data: sellers spanning all three risk bands.

Exists so the demo, the E2E suite and any UI work always have something
meaningful to render without first running the whole AI pipeline. Refuses to
run in production (see seed/run.py).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from trustlens.core.domain.enums import (
    AccountStatus,
    DocumentType,
    LineType,
    ListingSource,
    ListingStatus,
    RiskLevel,
    ScoreTrigger,
    SignalCategory,
    SignalCode,
    SignalStatus,
    UserRole,
    VerificationStatus,
)
from trustlens.db import models as m
from trustlens.db.seed.reference import SCORING_MODEL_ID, SIGNALS, _id
from trustlens.shared.config.settings import Settings
from trustlens.shared.crypto import Argon2PasswordHasher

NS_DEMO = UUID("6f1a9c30-0000-4000-8000-0000000000d0")


def _demo_id(kind: str, key: str) -> UUID:
    return uuid5(NS_DEMO, f"{kind}:{key}")


# (email, name, role, handle, target band, account age in days)
DEMO_USERS: tuple[tuple[str, str, UserRole, str | None, RiskLevel | None, int], ...] = (
    ("admin@trustlens.dev", "Demo Admin", UserRole.ADMIN, None, None, 400),
    ("reviewer@trustlens.dev", "Demo Reviewer", UserRole.REVIEWER, None, None, 400),
    ("buyer@trustlens.dev", "Demo Buyer", UserRole.BUYER, None, None, 200),
    (
        "seller.high@trustlens.dev",
        "Ayesha Traders",
        UserRole.SELLER,
        "ayesha-traders",
        RiskLevel.LOW,
        420,
    ),
    (
        "seller.mid@trustlens.dev",
        "Bilal Motors",
        UserRole.SELLER,
        "bilal-motors",
        RiskLevel.MEDIUM,
        95,
    ),
    (
        "seller.low@trustlens.dev",
        "Quick Deals PK",
        UserRole.SELLER,
        "quick-deals-pk",
        RiskLevel.HIGH,
        6,
    ),
)

DEMO_PASSWORDS = {
    UserRole.ADMIN: "Admin!Passw0rd123",
    UserRole.REVIEWER: "Review!Passw0rd123",
    UserRole.SELLER: "Seller!Passw0rd123",
    UserRole.BUYER: "Buyer!Passw0rd123",
}

#: Which signals each demo band passes. Chosen so the three sellers tell a
#: story: a fully verified trader, a partly verified one on a VOIP number, and
#: a brand-new account with a failed face match and pressure-tactic listings.
BAND_PROFILE: dict[RiskLevel, dict[SignalCode, SignalStatus]] = {
    RiskLevel.LOW: dict.fromkeys([code for code, *_ in SIGNALS], SignalStatus.PASS),
    RiskLevel.MEDIUM: {
        SignalCode.IDENTITY_DOCUMENT_VALID: SignalStatus.PASS,
        SignalCode.IDENTITY_FACE_MATCH: SignalStatus.PASS,
        SignalCode.PHONE_VERIFIED: SignalStatus.PASS,
        SignalCode.PHONE_NOT_DISPOSABLE: SignalStatus.FAIL,
        SignalCode.EMAIL_VERIFIED: SignalStatus.PASS,
        SignalCode.EMAIL_NOT_DISPOSABLE: SignalStatus.PASS,
        SignalCode.DEVICE_NOT_SHARED: SignalStatus.PARTIAL,
        SignalCode.DEVICE_CONSISTENT: SignalStatus.PASS,
        SignalCode.NETWORK_NOT_VPN: SignalStatus.FAIL,
        SignalCode.NETWORK_GEO_CONSISTENT: SignalStatus.UNAVAILABLE,
        SignalCode.ACCOUNT_AGE: SignalStatus.PARTIAL,
        SignalCode.ACTIVITY_CONSISTENT: SignalStatus.PASS,
        SignalCode.LISTING_CONTENT_SAFE: SignalStatus.PARTIAL,
        SignalCode.LISTING_PRICE_REALISTIC: SignalStatus.PASS,
    },
    RiskLevel.HIGH: {
        SignalCode.IDENTITY_DOCUMENT_VALID: SignalStatus.PASS,
        # A failed face match trips the hard cap, which is exactly the case
        # the demo needs to show: high scores elsewhere cannot rescue it.
        SignalCode.IDENTITY_FACE_MATCH: SignalStatus.FAIL,
        SignalCode.PHONE_VERIFIED: SignalStatus.PASS,
        SignalCode.PHONE_NOT_DISPOSABLE: SignalStatus.FAIL,
        SignalCode.EMAIL_VERIFIED: SignalStatus.PASS,
        SignalCode.EMAIL_NOT_DISPOSABLE: SignalStatus.FAIL,
        SignalCode.DEVICE_NOT_SHARED: SignalStatus.FAIL,
        SignalCode.DEVICE_CONSISTENT: SignalStatus.PASS,
        SignalCode.NETWORK_NOT_VPN: SignalStatus.FAIL,
        SignalCode.NETWORK_GEO_CONSISTENT: SignalStatus.FAIL,
        SignalCode.ACCOUNT_AGE: SignalStatus.FAIL,
        SignalCode.ACTIVITY_CONSISTENT: SignalStatus.PARTIAL,
        SignalCode.LISTING_CONTENT_SAFE: SignalStatus.FAIL,
        SignalCode.LISTING_PRICE_REALISTIC: SignalStatus.FAIL,
    },
}

REASONS: dict[tuple[SignalCode, SignalStatus], tuple[str, str]] = {
    (SignalCode.IDENTITY_DOCUMENT_VALID, SignalStatus.PASS): (
        "IDENTITY_VERIFIED",
        "A valid government ID was submitted and checked.",
    ),
    (SignalCode.IDENTITY_FACE_MATCH, SignalStatus.PASS): (
        "FACE_MATCH_HIGH",
        "The selfie matches the photo on the submitted ID.",
    ),
    (SignalCode.IDENTITY_FACE_MATCH, SignalStatus.FAIL): (
        "FACE_MATCH_LOW",
        "The selfie does not match the photo on the submitted ID.",
    ),
    (SignalCode.PHONE_NOT_DISPOSABLE, SignalStatus.FAIL): (
        "PHONE_LINE_TYPE_VOIP",
        "The phone number is an internet (VOIP) number rather than a mobile SIM.",
    ),
    (SignalCode.EMAIL_NOT_DISPOSABLE, SignalStatus.FAIL): (
        "EMAIL_DOMAIN_DISPOSABLE",
        "The email address uses a temporary email service.",
    ),
    (SignalCode.DEVICE_NOT_SHARED, SignalStatus.FAIL): (
        "DEVICE_SHARED_MANY_ACCOUNTS",
        "This device is linked to several other seller accounts.",
    ),
    (SignalCode.NETWORK_NOT_VPN, SignalStatus.FAIL): (
        "NETWORK_VPN_DETECTED",
        "The seller connects through a VPN, hiding their location.",
    ),
    (SignalCode.NETWORK_GEO_CONSISTENT, SignalStatus.FAIL): (
        "GEO_MISMATCH",
        "The seller's connection location does not match their stated location.",
    ),
    (SignalCode.ACCOUNT_AGE, SignalStatus.FAIL): (
        "ACCOUNT_TOO_NEW",
        "The account was created very recently.",
    ),
    (SignalCode.LISTING_CONTENT_SAFE, SignalStatus.FAIL): (
        "LISTING_URGENCY_PRESSURE",
        "Listings use pressure tactics such as 'pay now, others are waiting'.",
    ),
    (SignalCode.LISTING_PRICE_REALISTIC, SignalStatus.FAIL): (
        "PRICE_TOO_GOOD_TO_BE_TRUE",
        "Prices are far below the normal range for similar items.",
    ),
}

DEMO_LISTINGS: dict[RiskLevel, tuple[tuple[str, str, float, str], ...]] = {
    RiskLevel.LOW: (
        (
            "Samsung Galaxy A54 - 128GB, excellent condition",
            "Used for 8 months, box and receipt included. Meet at a public place, "
            "inspection welcome before payment.",
            72000,
            "Mobile Phones",
        ),
    ),
    RiskLevel.MEDIUM: (
        (
            "Honda City 2018 - low mileage",
            "Well maintained, single owner. Serious buyers only. Contact on WhatsApp "
            "for faster response.",
            3_450_000,
            "Cars",
        ),
    ),
    RiskLevel.HIGH: (
        (
            "iPhone 15 Pro Max SEALED - urgent sale today only!!",
            "Leaving country tomorrow, must sell TODAY. Price is final. Send advance "
            "payment to reserve, first come first served. Contact me on WhatsApp only, "
            "do not message here.",
            95_000,
            "Mobile Phones",
        ),
    ),
}


async def seed_demo_data(session, settings: Settings) -> dict[str, int]:
    hasher = Argon2PasswordHasher(settings.security)
    now = datetime.now(UTC)
    created = {"users": 0, "sellers": 0, "listings": 0, "scores": 0}

    definitions = {
        code: (_id("signal", code.value), category, float(points), cap)
        for code, category, points, _crit, cap, _n, _b in SIGNALS
    }

    for email, full_name, role, handle, band, age_days in DEMO_USERS:
        user_id = _demo_id("user", email)
        if await session.get(m.User, user_id) is not None:
            continue

        session.add(
            m.User(
                id=user_id,
                email=email,
                full_name=full_name,
                status=AccountStatus.ACTIVE,
                primary_role=role,
                email_verified_at=now,
                password_hash=hasher.hash(DEMO_PASSWORDS[role]),
                created_at=now - timedelta(days=age_days),
                updated_at=now,
            )
        )
        session.add(
            m.UserRoleLink(user_id=user_id, role_id=_id("role", role.value), granted_at=now)
        )
        # Buyers can also sell; the demo admin/reviewer keep buyer read access.
        if role in {UserRole.ADMIN, UserRole.REVIEWER, UserRole.SELLER}:
            session.add(
                m.UserRoleLink(
                    user_id=user_id, role_id=_id("role", UserRole.BUYER.value), granted_at=now
                )
            )
        created["users"] += 1

        # Flush before the dependent rows: SQLAlchemy batches inserts by table,
        # so without this it would try to insert email_addresses before users
        # and trip the foreign key.
        await session.flush()

        session.add(
            m.EmailAddressModel(
                id=_demo_id("email", email),
                user_id=user_id,
                email=email,
                domain=email.split("@")[1],
                is_primary=True,
                verified_at=now,
                is_disposable=(band is RiskLevel.HIGH),
                mx_valid=True,
                domain_age_days=3000 if band is not RiskLevel.HIGH else 20,
                created_at=now,
                updated_at=now,
            )
        )

        await session.flush()

        if handle is None or band is None:
            continue

        await _seed_seller(session, user_id, handle, full_name, band, age_days, now, definitions)
        created["sellers"] += 1
        created["listings"] += len(DEMO_LISTINGS[band])
        created["scores"] += 1

    await session.flush()
    return created


async def _seed_seller(
    session,
    user_id: UUID,
    handle: str,
    display_name: str,
    band: RiskLevel,
    age_days: int,
    now: datetime,
    definitions: dict,
) -> None:
    seller_id = _demo_id("seller", handle)
    opened = now - timedelta(days=age_days)
    profile = BAND_PROFILE[band]

    session.add(
        m.SellerProfile(
            id=seller_id,
            user_id=user_id,
            handle=handle,
            display_name=display_name,
            marketplace_id=_id("marketplace", "olx"),
            city="Lahore",
            country_code="PK",
            account_opened_at=opened,
            identity_status=(
                VerificationStatus.VERIFIED
                if profile[SignalCode.IDENTITY_FACE_MATCH] is SignalStatus.PASS
                else VerificationStatus.REJECTED
            ),
            phone_status=VerificationStatus.VERIFIED,
            email_status=VerificationStatus.VERIFIED,
            created_at=opened,
            updated_at=now,
        )
    )

    session.add(
        m.PhoneNumberModel(
            id=_demo_id("phone", handle),
            user_id=user_id,
            e164=f"+9230012{abs(hash(handle)) % 100000:05d}",
            is_primary=True,
            verified_at=now,
            line_type=(
                LineType.MOBILE
                if profile[SignalCode.PHONE_NOT_DISPOSABLE] is SignalStatus.PASS
                else LineType.VOIP
            ),
            country_code="PK",
            created_at=opened,
            updated_at=now,
        )
    )

    session.add(
        m.StoredFileModel(
            id=_demo_id("file", f"{handle}-front"),
            owner_user_id=user_id,
            purpose="CNIC_FRONT",
            bucket="trustlens-documents",
            object_key=f"demo/{handle}/cnic-front.jpg",
            mime_type="image/jpeg",
            size_bytes=1,
            sha256=b"\x00" * 32,
            created_at=opened,
            updated_at=now,
        )
    )
    await session.flush()

    session.add(
        m.IdentityDocumentModel(
            id=_demo_id("doc", handle),
            seller_id=seller_id,
            document_type=DocumentType.CNIC_FRONT,
            file_id=_demo_id("file", f"{handle}-front"),
            status=VerificationStatus.VERIFIED,
            ocr_engine="demo",
            ocr_confidence=0.94,
            extracted_name=display_name,
            created_at=opened,
            updated_at=now,
        )
    )
    for index, (title, description, price, category) in enumerate(DEMO_LISTINGS[band]):
        listing_id = _demo_id("listing", f"{handle}-{index}")
        session.add(
            m.ListingModel(
                id=listing_id,
                seller_id=seller_id,
                marketplace_id=_id("marketplace", "olx"),
                source=ListingSource.MANUAL,
                title=title,
                description=description,
                price=price,
                currency="PKR",
                category=category,
                city="Lahore",
                country_code="PK",
                status=ListingStatus.ACTIVE,
                posted_at=now - timedelta(days=index + 1),
                created_at=now - timedelta(days=index + 1),
                updated_at=now,
            )
        )

    await session.flush()
    _seed_score(session, seller_id, band, profile, definitions, now)


#: Fallbacks for (signal, status) pairs the demo does not spell out. Kept
#: honest per status - a PARTIAL signal captioned "This check passed" would
#: contradict the negative impact shown next to it.
_FALLBACK_REASONS: dict[SignalStatus, tuple[str, str]] = {
    SignalStatus.PASS: ("IDENTITY_VERIFIED", "This check passed."),
    SignalStatus.PARTIAL: ("ACTIVITY_IRREGULAR", "This check passed only partly."),
    SignalStatus.FAIL: ("ADMIN_FLAGGED", "This check did not pass."),
    SignalStatus.UNAVAILABLE: ("SIGNAL_UNAVAILABLE", "This check could not be completed."),
    SignalStatus.NOT_APPLICABLE: ("NO_LISTINGS", "This check does not apply yet."),
}


def _fallback_reason(status: SignalStatus) -> tuple[str, str]:
    return _FALLBACK_REASONS[status]


def _seed_score(
    session,
    seller_id: UUID,
    band: RiskLevel,
    profile: dict[SignalCode, SignalStatus],
    definitions: dict,
    now: datetime,
) -> None:
    """Build a score using the same arithmetic as the real engine.

    Deliberately not hard-coded numbers: if the weights or the algorithm
    change, the demo data changes with them rather than silently disagreeing
    with what the engine would actually produce.
    """
    ratio_for = {
        SignalStatus.PASS: 1.0,
        SignalStatus.PARTIAL: 0.5,
        SignalStatus.FAIL: 0.0,
    }

    score_id = _demo_id("score", str(seller_id))
    earned = available = 0.0
    cap_applied: int | None = None
    rows: list[m.TrustScoreSignalModel] = []

    for code, (definition_id, category, points, cap) in definitions.items():
        status = profile.get(code, SignalStatus.UNAVAILABLE)
        counts = status in {SignalStatus.PASS, SignalStatus.PARTIAL, SignalStatus.FAIL}
        awarded = points * ratio_for.get(status, 0.0) if counts else 0.0
        possible = points if counts else 0.0
        earned += awarded
        available += possible

        if status is SignalStatus.FAIL and cap is not None:
            cap_applied = cap if cap_applied is None else min(cap_applied, cap)

        reason_code, reason_text = REASONS.get((code, status), _fallback_reason(status))
        rows.append(
            m.TrustScoreSignalModel(
                id=_demo_id("signal", f"{seller_id}:{code.value}"),
                trust_score_id=score_id,
                signal_definition_id=definition_id,
                signal_code=code.value,
                category=SignalCategory(category),
                status=status,
                weight=points,
                points_awarded=round(awarded, 3),
                points_possible=possible,
                confidence=0.9 if counts else 0.0,
                reason_code=reason_code,
                reason_text=reason_text,
                evidence={},
            )
        )

    raw = (earned / available) * 100 if available else 0.0
    final = min(raw, float(cap_applied)) if cap_applied is not None else raw
    final_int = max(0, min(100, round(final)))

    session.add(
        m.TrustScoreModel(
            id=score_id,
            seller_id=seller_id,
            scoring_model_id=SCORING_MODEL_ID,
            score=final_int,
            risk_level=band,
            raw_score=round(raw, 3),
            available_weight=round(available, 3),
            cap_applied=cap_applied,
            confidence=0.85,
            trigger=ScoreTrigger.MANUAL,
            is_current=True,
            computed_at=now,
            valid_until=now + timedelta(days=30),
        )
    )
    for row in rows:
        session.add(row)


__all__ = ["DEMO_PASSWORDS", "DEMO_USERS", "seed_demo_data"]
