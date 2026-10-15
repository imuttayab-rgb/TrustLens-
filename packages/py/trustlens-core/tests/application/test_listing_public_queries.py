"""Fail-closed buyer query contract tests; no local PostgreSQL is modified."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from trustlens.core.domain.enums import ListingStatus
from trustlens.db.repositories import SqlFavoriteRepository, SqlListingRepository


def assert_seller_gate(stmt: Any) -> None:
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    for column in ("identity_status", "phone_status", "email_status", "is_flagged"):
        assert f"seller_profiles.{column}" in sql
    assert "listings.deleted_at IS NULL" in sql
    assert "seller_profiles.deleted_at IS NULL" in sql


def test_marketplace_and_count_share_verification_gate() -> None:
    repository = SqlListingRepository(cast(Any, None))
    stmt = repository._public_query_base(category=None, q=None)
    assert_seller_gate(stmt)
    assert "listings.status" in str(stmt.compile(dialect=postgresql.dialect()))


class FakeResult:
    def first(self) -> None:
        return None

    def all(self) -> list[Any]:
        return []

    def scalar_one(self) -> int:
        return 0

    def scalar_one_or_none(self) -> UUID:
        return UUID(int=1)


class SqlCapture:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> FakeResult:
        self.statements.append(stmt)
        return FakeResult()


@pytest.mark.asyncio
async def test_direct_listing_lookup_gates_unverified_seller() -> None:
    session = SqlCapture()
    assert await SqlListingRepository(cast(Any, session)).get_public_detail(UUID(int=1)) is None
    assert_seller_gate(session.statements[0])


@pytest.mark.asyncio
async def test_saved_listing_and_count_cannot_bypass_public_gate() -> None:
    session = SqlCapture()
    repository = SqlFavoriteRepository(cast(Any, session))
    assert await repository.list_favorite_listings(UUID(int=2)) == []
    assert await repository.count_for_user(UUID(int=2)) == 0
    for stmt in session.statements:
        assert_seller_gate(stmt)


@pytest.mark.asyncio
async def test_status_change_is_atomic_without_overwriting_listing_content() -> None:
    session = SqlCapture()
    changed = await SqlListingRepository(cast(Any, session)).set_publication_status_if_current(
        UUID(int=1), from_status=ListingStatus.DRAFT, to_status=ListingStatus.ACTIVE,
        expected_version=4, expected_analysis_id=UUID(int=8), at=datetime.now(UTC),
    )
    assert changed
    sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    update_part, where_part = sql.split(" WHERE ", maxsplit=1)
    assert " SET status=" in update_part
    assert "latest_analysis_id" not in update_part
    assert "title" not in update_part
    assert "listings.version" in where_part
    assert "listings.latest_analysis_id" in where_part
