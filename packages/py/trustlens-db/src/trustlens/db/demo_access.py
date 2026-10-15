"""Revocable marketplace access for the original 50 synthetic local fixtures.

This is an access exception, never evidence of identity or face verification.
There is no HTTP endpoint that grants it, and no prefix-based enrollment.
"""
from uuid import UUID, uuid5

from sqlalchemy import false, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import aliased

from trustlens.core.domain.enums import AccountStatus
from trustlens.db import models as m

BATCH = "trustlens-test-users-50-v1"
NAMESPACE = UUID("d3d47974-dc61-431f-9ea5-617f29bd7768")
LOCAL_HOSTS = {"postgres", "db", "localhost", "127.0.0.1", "::1"}


def fixtures():
    return tuple(
        {
            "number": n,
            "email": f"test.seller{n:02d}@trustlens.dev",
            "user_id": uuid5(NAMESPACE, f"user:test.seller{n:02d}@trustlens.dev"),
            "seller_id": uuid5(NAMESPACE, f"seller:test-seller-{n:02d}"),
            "external_ref": f"{BATCH}:{n:02d}",
        }
        for n in range(1, 51)
    )


FIXTURES = fixtures()
FIXTURE_IDS = tuple(row["user_id"] for row in FIXTURES)


def local_demo_enabled(settings=None):
    if settings is None:
        from trustlens.shared.config import get_settings
        settings = get_settings()
    return bool(
        settings.env.value in {"development", "test", "staging"}
        and settings.ai.use_fake_ai
        and not settings.database.db_echo
        and (make_url(settings.database.database_url).host or "").lower() in LOCAL_HOSTS
        and settings.storage.storage_provider == "s3"
        and settings.storage.storage_endpoint_url
        and (make_url(settings.storage.storage_endpoint_url).host or "").lower()
        in LOCAL_HOSTS | {"minio"}
    )


def temporary_test_access(user_id):
    if not local_demo_enabled():
        return false()
    grant, user, seller = (aliased(c) for c in (m.DemoProfileAccessModel, m.User, m.SellerProfile))
    return (
        select(grant.user_id)
        .join(user, user.id == grant.user_id)
        .join(seller, seller.id == grant.seller_id)
        .where(
            grant.user_id == user_id,
            grant.user_id.in_(FIXTURE_IDS),
            grant.batch == BATCH,
            grant.enabled.is_(True),
            grant.revoked_at.is_(None),
            user.email == grant.enrolled_email,
            user.created_at == grant.account_created_at,
            user.created_at < grant.enrolled_at,
            user.status == AccountStatus.ACTIVE,
            user.deleted_at.is_(None),
            seller.user_id == user.id,
            seller.external_seller_ref == grant.fixture_ref,
            seller.deleted_at.is_(None),
            seller.is_flagged.is_(False),
        )
        .correlate_except(grant, user, seller)
        .exists()
    )


def fixture_label(user_id):
    for row in FIXTURES:
        if row["user_id"] == user_id:
            return f'Test Seller {row["number"]:02d} (Demo)'
    return "Member"
