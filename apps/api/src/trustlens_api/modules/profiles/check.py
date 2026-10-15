"""Read-only profile installation diagnostics. No names, keys or customer data printed."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select, text

from trustlens.db import models as m
from trustlens.db.profiles import (
    listing_not_paused,
    listing_profile_ready,
    name_verified,
    profile_ready,
)
from trustlens.db.session import create_engine, create_session_factory
from trustlens.shared.config import get_settings


async def run():
    engine = create_engine(get_settings().database)
    factory = create_session_factory(engine)
    try:
        async with factory() as session, factory() as other:
            for model in (
                m.AccountProfileModel,
                m.ProfilePhotoModel,
                m.ProfileNameRequestModel,
                m.ProfileHandleAliasModel,
                m.ListingPauseModel,
            ):
                await session.execute(select(model).limit(0))
            assert not (await session.execute(select(profile_ready(uuid4())))).scalar_one()
            await session.execute(select(m.User.id).where(name_verified(m.User.id)).limit(1))
            await session.execute(
                select(m.ListingModel.id)
                .where(listing_profile_ready(), listing_not_paused())
                .limit(1)
            )
            await session.execute(text("SELECT pg_advisory_xact_lock(847392109)"))
            assert not (
                await other.execute(text("SELECT pg_try_advisory_xact_lock(847392109)"))
            ).scalar_one()
            await session.rollback()
            assert (
                await other.execute(text("SELECT pg_try_advisory_xact_lock(847392109)"))
            ).scalar_one()
            await other.rollback()
            print(
                "PROFILE_SCHEMA=PASS\nPROFILE_PUBLICATION_QUERY=PASS\nUSERNAME_LOCK_SERIALIZATION=PASS\nUNKNOWN_USER_ACCESS=DENIED"
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
