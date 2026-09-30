"""Demo data: sellers spanning all three risk bands.

Exists so the demo, the E2E suite and any UI work always have something
meaningful to render without first running the whole AI pipeline. Refuses to
run in production (see seed/run.py).
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trustlens.core.domain.enums import (
    AccountStatus,
    DocumentType,
    FilePurpose,
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
from trustlens.core.domain.ports import ObjectStorage
from trustlens.db import models as m
from trustlens.db.seed.reference import SCORING_MODEL_ID, SIGNALS, _id
from trustlens.shared.config.settings import Settings
from trustlens.shared.crypto import Argon2PasswordHasher
from trustlens.shared.storage import build_storage

NS_DEMO = UUID("6f1a9c30-0000-4000-8000-0000000000d0")

#: Deterministic per-category palettes so re-seeding always produces the same
#: images (matters for reproducible screenshots and E2E snapshots).
_PLACEHOLDER_PALETTES: dict[str, tuple[str, str]] = {
    "mobiles": ("#0f766e", "#5eead4"),
    "vehicles": ("#334155", "#93c5fd"),
    "property-sale": ("#78350f", "#fbbf24"),
    "electronics": ("#1e3a8a", "#93c5fd"),
    "home-appliances": ("#4c1d95", "#c4b5fd"),
    "services": ("#155e75", "#67e8f9"),
    "fashion": ("#831843", "#f9a8d4"),
}
_PLACEHOLDER_FALLBACK = ("#374151", "#9ca3af")
_PLACEHOLDER_SIZE = (1024, 768)

#: Mirrors `LISTING_CATEGORY_LABELS` in packages/constants for the handful of
#: categories demo listings actually use - the stored `category` stays the
#: real slug (so filtering works), this is display text only.
_CATEGORY_LABELS: dict[str, str] = {
    "mobiles": "Mobile Phones",
    "vehicles": "Vehicles",
    "property-sale": "Property for Sale",
    "electronics": "Electronics",
    "home-appliances": "Home Appliances",
    "services": "Services",
    "fashion": "Fashion",
}


def _generate_placeholder_image(title: str, category: str) -> bytes:
    """Render a simple branded placeholder JPEG for a demo listing photo.

    Not stock photography - just an abstract, category-labelled graphic so
    listing cards render a real image instead of the broken-image icon. Pure
    Pillow, no external font/asset dependency, so it runs anywhere.
    """
    bg_hex, accent_hex = _PLACEHOLDER_PALETTES.get(category, _PLACEHOLDER_FALLBACK)
    bg = tuple(int(bg_hex[i : i + 2], 16) for i in (1, 3, 5))
    accent = tuple(int(accent_hex[i : i + 2], 16) for i in (1, 3, 5))

    width, height = _PLACEHOLDER_SIZE
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)

    # A couple of soft decorative circles, positioned deterministically from
    # the title so different listings in the same category still look distinct.
    seed = int(hashlib.sha256(title.encode()).hexdigest(), 16)
    for i in range(3):
        r = 90 + ((seed >> (i * 8)) % 160)
        cx = (seed >> (i * 16 + 8)) % width
        cy = (seed >> (i * 16 + 16)) % height
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=accent,
            width=6,
        )

    category_font = ImageFont.load_default(size=56)
    caption_font = ImageFont.load_default(size=28)

    category_text = _CATEGORY_LABELS.get(category, category).upper()
    bbox = draw.textbbox((0, 0), category_text, font=category_font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((width - text_w) / 2, (height - text_h) / 2 - 10),
        category_text,
        font=category_font,
        fill=accent,
        anchor=None,
    )

    caption = "Demo listing photo"
    cap_bbox = draw.textbbox((0, 0), caption, font=caption_font)
    cap_w = cap_bbox[2] - cap_bbox[0]
    draw.text(
        ((width - cap_w) / 2, height - 60),
        caption,
        font=caption_font,
        fill=accent,
    )

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


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
            "mobiles",
        ),
    ),
    RiskLevel.MEDIUM: (
        (
            "Honda City 2018 - low mileage",
            "Well maintained, single owner. Serious buyers only. Contact on WhatsApp "
            "for faster response.",
            3_450_000,
            "vehicles",
        ),
    ),
    RiskLevel.HIGH: (
        (
            "iPhone 15 Pro Max SEALED - urgent sale today only!!",
            "Leaving country tomorrow, must sell TODAY. Price is final. Send advance "
            "payment to reserve, first come first served. Contact me on WhatsApp only, "
            "do not message here.",
            95_000,
            "mobiles",
        ),
    ),
}

#: Real, well-known public places in Lahore - every demo seller uses that
#: city, and SafeMeet has nothing to suggest without at least a few curated
#: venues to pick from (SAFE-01 is staff-curated, never a party's home
#: address). Approximate coordinates, good enough for a demo map pin.
DEMO_MEETING_VENUES: tuple[tuple[str, str, str, float, float], ...] = (
    (
        "Packages Mall",
        "Package Mall Road, Walton Road, Lahore",
        "Walton",
        31.4697,
        74.2728,
    ),
    (
        "Emporium Mall",
        "Bedian Road, Lahore",
        "Bedian Road",
        31.4790,
        74.2728,
    ),
    (
        "Fortress Square Mall",
        "Fortress Stadium, Lahore Cantt",
        "Cantt",
        31.5075,
        74.3540,
    ),
)


async def _ensure_demo_meeting_venues(session: AsyncSession, now: datetime) -> int:
    added = 0
    for name, address, area, latitude, longitude in DEMO_MEETING_VENUES:
        venue_id = _demo_id("venue", name)
        if await session.get(m.MeetingVenueModel, venue_id) is not None:
            continue
        session.add(
            m.MeetingVenueModel(
                id=venue_id,
                name=name,
                address=address,
                city="Lahore",
                area=area,
                latitude=latitude,
                longitude=longitude,
                is_active=True,
                notes="Seeded demo venue.",
                created_at=now,
            )
        )
        added += 1
    return added


async def seed_demo_data(session: AsyncSession, settings: Settings) -> dict[str, int]:
    hasher = Argon2PasswordHasher(settings.security)
    storage = build_storage(settings.storage)
    now = datetime.now(UTC)
    created = {
        "users": 0,
        "sellers": 0,
        "listings": 0,
        "scores": 0,
        "images_backfilled": 0,
        "venues": 0,
    }

    definitions = {
        code: (_id("signal", code.value), category, float(points), cap)
        for code, category, points, _crit, cap, _n, _b in SIGNALS
    }

    for email, full_name, role, handle, band, age_days in DEMO_USERS:
        user_id = _demo_id("user", email)
        if await session.get(m.User, user_id) is not None:
            # Already seeded in an earlier run. Still backfill listing photos
            # for dev DBs created before image generation existed, without
            # touching anything else about this user (real conversations,
            # offers, etc. may already hang off it from live testing).
            if handle is not None and band is not None:
                created["images_backfilled"] += await _ensure_demo_listing_images(
                    session, storage, settings, user_id, handle, band, now
                )
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

        await _seed_seller(
            session, user_id, handle, full_name, band, age_days, now, definitions, storage, settings
        )
        created["sellers"] += 1
        created["listings"] += len(DEMO_LISTINGS[band])
        created["scores"] += 1

    created["venues"] = await _ensure_demo_meeting_venues(session, now)

    await session.flush()
    return created


async def _seed_listing_image(
    session: AsyncSession,
    storage: ObjectStorage,
    settings: Settings,
    user_id: UUID,
    listing_id: UUID,
    handle: str,
    index: int,
    title: str,
    category: str,
    now: datetime,
) -> None:
    file_id = _demo_id("file", f"{handle}-{index}-image")
    object_key = f"demo/listings/{handle}-{index}.jpg"
    image_bytes = _generate_placeholder_image(title, category)

    await storage.put(
        bucket=settings.storage.storage_bucket_listings,
        object_key=object_key,
        data=image_bytes,
        content_type="image/jpeg",
        # Public listing photos, not sensitive documents - and dev/test S3
        # backends (MinIO) often can't do SSE-S3 without a KMS they don't have.
        server_side_encryption=False,
    )

    session.add(
        m.StoredFileModel(
            id=file_id,
            owner_user_id=user_id,
            purpose=FilePurpose.LISTING_IMAGE,
            bucket=settings.storage.storage_bucket_listings,
            object_key=object_key,
            mime_type="image/jpeg",
            size_bytes=len(image_bytes),
            sha256=hashlib.sha256(image_bytes).digest(),
            width=_PLACEHOLDER_SIZE[0],
            height=_PLACEHOLDER_SIZE[1],
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()
    session.add(
        m.ListingImageModel(
            id=_demo_id("listing_image", f"{handle}-{index}"),
            listing_id=listing_id,
            file_id=file_id,
            position=0,
            width=_PLACEHOLDER_SIZE[0],
            height=_PLACEHOLDER_SIZE[1],
            sha256=hashlib.sha256(image_bytes).digest(),
            is_primary=True,
            created_at=now,
        )
    )


async def _ensure_demo_listing_images(
    session: AsyncSession,
    storage: ObjectStorage,
    settings: Settings,
    user_id: UUID,
    handle: str,
    band: RiskLevel,
    now: datetime,
) -> int:
    """Bring demo listings already in the DB in line with the current
    `DEMO_LISTINGS` - photos for rows seeded before image generation existed,
    and the category corrected for rows seeded back when it held a display
    label ("Mobile Phones") instead of the real filter slug ("mobiles"),
    which silently broke category search for exactly these listings.

    Only touches what's actually out of date, so re-running against a dev DB
    that's already current (or already exercised via live testing) is a
    no-op for those rows.
    """
    added = 0
    for index, (title, _description, _price, category) in enumerate(DEMO_LISTINGS[band]):
        listing_id = _demo_id("listing", f"{handle}-{index}")

        listing = await session.get(m.ListingModel, listing_id)
        if listing is not None and listing.category != category:
            listing.category = category
            listing.updated_at = now

        existing = await session.execute(
            select(m.ListingImageModel.id).where(m.ListingImageModel.listing_id == listing_id)
        )
        if existing.first() is not None:
            continue
        await _seed_listing_image(
            session, storage, settings, user_id, listing_id, handle, index, title, category, now
        )
        added += 1
    return added


async def _seed_seller(
    session: AsyncSession,
    user_id: UUID,
    handle: str,
    display_name: str,
    band: RiskLevel,
    age_days: int,
    now: datetime,
    definitions: Mapping[SignalCode, tuple[UUID, SignalCategory, float, int | None]],
    storage: ObjectStorage,
    settings: Settings,
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

    for index, (title, _description, _price, category) in enumerate(DEMO_LISTINGS[band]):
        listing_id = _demo_id("listing", f"{handle}-{index}")
        await _seed_listing_image(
            session, storage, settings, user_id, listing_id, handle, index, title, category, now
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
    session: AsyncSession,
    seller_id: UUID,
    band: RiskLevel,
    profile: dict[SignalCode, SignalStatus],
    definitions: Mapping[SignalCode, tuple[UUID, SignalCategory, float, int | None]],
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
