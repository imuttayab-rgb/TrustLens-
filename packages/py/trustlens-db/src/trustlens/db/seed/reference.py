"""Reference data: roles, permissions, signal definitions and scoring model v1.

Idempotent upserts - safe to re-run on every deploy. This is the data the
system genuinely cannot start without: with no active scoring model,
ComputeTrustScore raises NoActiveScoringModel and nothing can be scored.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trustlens.core.domain.enums import SignalCategory, SignalCode, UserRole
from trustlens.db import models as m

#: Deterministic ids derived from a namespace, so a re-seed updates the same
#: rows rather than creating duplicates, and ids are identical across
#: environments (which makes fixtures and support queries portable).
NS = UUID("6f1a9c30-0000-4000-8000-000000000001")


def _id(kind: str, key: str) -> UUID:
    return uuid5(NS, f"{kind}:{key}")


# ── Permissions (docs/09 matrix) ─────────────────────────────────────

PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("seller:read:public", "Public seller score page"),
    ("seller:read:self", "Read own seller profile"),
    ("seller:read:any", "Read any seller profile"),
    ("seller:write:self", "Update own seller profile"),
    ("seller:flag", "Flag a seller for review"),
    ("seller:suspend", "Suspend a seller account"),
    ("identity:submit", "Submit identity documents"),
    ("identity:read:self", "Read own identity verification status"),
    ("identity:read:any", "View submitted identity documents"),
    ("identity:approve", "Approve an identity verification"),
    ("identity:reject", "Reject an identity verification"),
    ("contact:verify:self", "Verify own phone and email"),
    ("listing:read:self", "Read own listings"),
    ("listing:read:any", "Read any listing"),
    ("listing:write:self", "Create and edit own listings"),
    ("listing:analyse", "Trigger listing analysis"),
    ("trust_score:read:public", "Read the public trust score"),
    ("trust_score:read:full", "Read the full score breakdown"),
    ("trust_score:recompute", "Trigger a score recomputation"),
    ("trust_score:override", "Override a computed score"),
    ("appeal:create", "Submit an appeal"),
    ("appeal:read:self", "Read own appeals"),
    ("appeal:read:any", "Read any appeal"),
    ("appeal:assign", "Assign an appeal to a reviewer"),
    ("appeal:resolve", "Resolve an appeal"),
    ("review_case:read", "Read the review queue"),
    ("review_case:decide", "Decide a review case"),
    ("moderation:read", "Read the reports queue"),
    ("moderation:resolve", "Resolve a report"),
    ("safemeet:manage", "Curate the SafeMeet venue catalogue"),
    ("scoring_model:read", "Read scoring models"),
    ("scoring_model:write", "Create or edit a scoring model"),
    ("scoring_model:simulate", "Simulate a scoring model"),
    ("scoring_model:activate", "Activate a scoring model"),
    ("api_client:read", "Read API clients"),
    ("api_client:create", "Create API clients and keys"),
    ("api_client:update", "Update API clients"),
    ("api_client:revoke", "Revoke API keys"),
    ("audit_log:read", "Read audit logs"),
    ("user:read:any", "Read any user"),
    ("user:manage_roles", "Grant or revoke roles"),
    ("job:read", "Read job status"),
    ("job:retry", "Retry a dead-lettered job"),
    ("metrics:read", "Read operational metrics"),
)

BUYER_PERMISSIONS = frozenset(
    {"seller:read:public", "trust_score:read:public", "contact:verify:self"}
)

SELLER_PERMISSIONS = BUYER_PERMISSIONS | {
    "seller:read:self",
    "seller:write:self",
    "identity:submit",
    "identity:read:self",
    "listing:read:self",
    "listing:write:self",
    "listing:analyse",
    "trust_score:read:full",
    "trust_score:recompute",
    "appeal:create",
    "appeal:read:self",
    "job:read",
}

#: A reviewer works the queue but deliberately CANNOT override a score or
#: manage roles - that keeps their power proportional to the job and stops the
#: queue role becoming a privilege-escalation path (docs/09 section 2).
REVIEWER_PERMISSIONS = BUYER_PERMISSIONS | {
    "seller:read:any",
    "seller:flag",
    "identity:read:any",
    "identity:approve",
    "identity:reject",
    "listing:read:any",
    "listing:analyse",
    "trust_score:read:full",
    "trust_score:recompute",
    "appeal:read:any",
    "appeal:assign",
    "appeal:resolve",
    "review_case:read",
    "review_case:decide",
    "moderation:read",
    "moderation:resolve",
    "safemeet:manage",
    "scoring_model:read",
    "user:read:any",
    "job:read",
    "metrics:read",
}

ADMIN_PERMISSIONS = frozenset(key for key, _ in PERMISSIONS)

ROLE_PERMISSIONS: dict[UserRole, frozenset[str]] = {
    UserRole.BUYER: BUYER_PERMISSIONS,
    UserRole.SELLER: SELLER_PERMISSIONS,
    UserRole.REVIEWER: REVIEWER_PERMISSIONS,
    UserRole.ADMIN: ADMIN_PERMISSIONS,
}

ROLE_NAMES: dict[UserRole, str] = {
    UserRole.BUYER: "Buyer",
    UserRole.SELLER: "Seller",
    UserRole.REVIEWER: "Reviewer",
    UserRole.ADMIN: "Administrator",
}


# ── Signal definitions and v1 weights ────────────────────────────────

# (code, category, points, critical, hard_cap_on_fail, name, buyer-facing text)
# Weights sum to exactly 100. Every one traces to a fraud pattern named in the
# proposal's problem statement - see docs/08 section 2.
SIGNALS: tuple[tuple[SignalCode, SignalCategory, int, bool, int | None, str, str], ...] = (
    (
        SignalCode.IDENTITY_DOCUMENT_VALID,
        SignalCategory.IDENTITY,
        15,
        True,
        20,
        "Valid ID document",
        "A valid government ID was submitted and read successfully.",
    ),
    (
        SignalCode.IDENTITY_FACE_MATCH,
        SignalCategory.IDENTITY,
        15,
        True,
        25,
        "Selfie matches ID",
        "The seller's selfie matches the photo on their ID.",
    ),
    (
        SignalCode.PHONE_VERIFIED,
        SignalCategory.PHONE,
        10,
        False,
        None,
        "Phone verified",
        "The phone number was confirmed with a one-time code.",
    ),
    (
        SignalCode.PHONE_NOT_DISPOSABLE,
        SignalCategory.PHONE,
        5,
        False,
        None,
        "Real mobile number",
        "The number is a mobile SIM rather than a throwaway internet number.",
    ),
    (
        SignalCode.EMAIL_VERIFIED,
        SignalCategory.EMAIL,
        6,
        False,
        None,
        "Email verified",
        "The email address was confirmed.",
    ),
    (
        SignalCode.EMAIL_NOT_DISPOSABLE,
        SignalCategory.EMAIL,
        4,
        False,
        None,
        "Permanent email",
        "The email address is not from a temporary email service.",
    ),
    (
        SignalCode.DEVICE_NOT_SHARED,
        SignalCategory.DEVICE,
        6,
        False,
        None,
        "Device not shared",
        "This device is not linked to a cluster of other seller accounts.",
    ),
    (
        SignalCode.DEVICE_CONSISTENT,
        SignalCategory.DEVICE,
        4,
        False,
        None,
        "Ordinary device",
        "The account is used from a real device, not an emulator or bot.",
    ),
    (
        SignalCode.NETWORK_NOT_VPN,
        SignalCategory.NETWORK,
        6,
        False,
        None,
        "No VPN or proxy",
        "The seller is not hiding their location behind a VPN or proxy.",
    ),
    (
        SignalCode.NETWORK_GEO_CONSISTENT,
        SignalCategory.NETWORK,
        4,
        False,
        None,
        "Location consistent",
        "The seller's connection location matches their stated location.",
    ),
    (
        SignalCode.ACCOUNT_AGE,
        SignalCategory.BEHAVIOUR,
        6,
        False,
        None,
        "Account age",
        "How long this seller account has existed.",
    ),
    (
        SignalCode.ACTIVITY_CONSISTENT,
        SignalCategory.BEHAVIOUR,
        4,
        False,
        None,
        "Regular activity",
        "The account is used regularly rather than in a single burst.",
    ),
    (
        SignalCode.LISTING_CONTENT_SAFE,
        SignalCategory.LISTING,
        10,
        False,
        None,
        "Listings look genuine",
        "Listings do not use wording commonly found in scams.",
    ),
    (
        SignalCode.LISTING_PRICE_REALISTIC,
        SignalCategory.LISTING,
        5,
        False,
        None,
        "Realistic prices",
        "Prices are in line with similar items, not 'too good to be true'.",
    ),
)

SCORING_MODEL_ID = _id("scoring_model", "v1.0")
SCORING_MODEL_VERSION = "v1.0"


async def seed_reference_data(session: AsyncSession) -> dict[str, int]:
    """Insert or update all reference data. Idempotent."""
    counts = {"permissions": 0, "roles": 0, "signals": 0, "weights": 0, "marketplaces": 0}

    # Permissions
    for key, description in PERMISSIONS:
        resource, _, action = key.partition(":")
        await _upsert(
            session,
            m.Permission,
            _id("permission", key),
            key=key,
            resource=resource,
            action=action,
            description=description,
        )
        counts["permissions"] += 1

    await session.flush()

    # Roles + role_permissions
    for role_key, permission_keys in ROLE_PERMISSIONS.items():
        role_id = _id("role", role_key.value)
        await _upsert(
            session,
            m.Role,
            role_id,
            key=role_key,
            name=ROLE_NAMES[role_key],
            description=f"{ROLE_NAMES[role_key]} role",
            is_system=True,
        )
        counts["roles"] += 1

        existing = set(
            (
                await session.execute(
                    select(m.RolePermission.permission_id).where(
                        m.RolePermission.role_id == role_id
                    )
                )
            )
            .scalars()
            .all()
        )
        for permission_key in permission_keys:
            permission_id = _id("permission", permission_key)
            if permission_id not in existing:
                session.add(m.RolePermission(role_id=role_id, permission_id=permission_id))

    await session.flush()

    # Signal definitions
    for order, (code, category, points, critical, _cap, name, buyer_text) in enumerate(SIGNALS):
        await _upsert(
            session,
            m.SignalDefinitionModel,
            _id("signal", code.value),
            code=code.value,
            category=category,
            name=name,
            description=name,
            buyer_facing_description=buyer_text,
            max_points=points,
            is_active=True,
            is_critical=critical,
            display_order=order,
        )
        counts["signals"] += 1

    await session.flush()

    # Scoring model v1 + weights
    total = sum(points for _c, _cat, points, _crit, _cap, _n, _b in SIGNALS)
    if total != 100:
        raise ValueError(f"v1 signal weights must sum to 100, got {total}")

    await _upsert(
        session,
        m.ScoringModelRow,
        SCORING_MODEL_ID,
        version=SCORING_MODEL_VERSION,
        name="TrustLens scoring model v1.0",
        description=(
            "Baseline weighted model. 14 signals across 7 categories, "
            "summing to 100 points, with hard caps on the two critical "
            "identity signals."
        ),
        is_active=True,
        algorithm="WEIGHTED_SUM",
        config={"min_evidence_weight": 40, "risk_bands": {"high": 39, "medium": 69}},
        activated_at=datetime.now(UTC),
    )
    await session.flush()

    for code, _category, points, _critical, cap, _name, _buyer in SIGNALS:
        await _upsert(
            session,
            m.ScoringWeightModel,
            _id("weight", f"{SCORING_MODEL_VERSION}:{code.value}"),
            scoring_model_id=SCORING_MODEL_ID,
            signal_definition_id=_id("signal", code.value),
            weight=float(points),
            hard_cap_on_fail=cap,
            is_enabled=True,
            threshold_config={},
        )
        counts["weights"] += 1

    # Example marketplaces from the proposal's target-user list
    for slug, name in (
        ("olx", "OLX-style general marketplace"),
        ("rentals", "Rental and property portal"),
        ("vehicles", "Second-hand vehicle site"),
        ("freelance", "Freelance / peer-to-peer platform"),
    ):
        await _upsert(
            session,
            m.Marketplace,
            _id("marketplace", slug),
            name=name,
            slug=slug,
            is_active=True,
        )
        counts["marketplaces"] += 1

    await session.flush()
    return counts


async def _upsert(session: AsyncSession, model: type[Any], row_id: UUID, **values: object) -> None:
    existing = await session.get(model, row_id)
    if existing is None:
        session.add(model(id=row_id, **values))
        return
    for key, value in values.items():
        # Never flip is_active back on for a model an admin deactivated - a
        # re-seed must not silently resurrect a retired scoring model.
        if key == "is_active" and model is m.ScoringModelRow:
            continue
        setattr(existing, key, value)


__all__ = [
    "ADMIN_PERMISSIONS",
    "PERMISSIONS",
    "ROLE_PERMISSIONS",
    "SCORING_MODEL_ID",
    "SCORING_MODEL_VERSION",
    "SIGNALS",
    "seed_reference_data",
]
