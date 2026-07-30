"""Async engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from trustlens.shared.config.settings import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    connect_args: dict[str, object] = {
        # Caps runaway admin queries at the server rather than relying on a
        # client-side timeout that a hung connection would never honour.
        "server_settings": {"statement_timeout": str(settings.db_statement_timeout_ms)},
    }
    if settings.db_ssl_require:
        connect_args["ssl"] = "require"

    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        # Recycle before the provider's idle timeout, otherwise the first
        # query after a quiet period fails on a server-closed connection.
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,  # entities stay usable after commit
        autoflush=False,  # flush points are explicit, in the use case
    )


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    session = factory()
    try:
        yield session
    finally:
        await session.close()


__all__ = ["create_engine", "create_session_factory", "session_scope"]
