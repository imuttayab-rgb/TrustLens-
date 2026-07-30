"""Seed entrypoint:  python -m trustlens.db.seed.run [reference|demo|all]"""

from __future__ import annotations

import asyncio
import sys

from trustlens.db.seed.demo import seed_demo_data
from trustlens.db.seed.reference import seed_reference_data
from trustlens.db.session import create_engine, create_session_factory
from trustlens.shared.config.settings import Environment, get_settings


async def main(target: str) -> int:
    settings = get_settings()

    # A test suite or seed script that can reach production is a production
    # incident waiting for a bad .env.
    if target in {"demo", "all"} and settings.env is Environment.PRODUCTION:
        print("!! Refusing to seed demo data in production.", file=sys.stderr)
        return 1

    engine = create_engine(settings.database)
    factory = create_session_factory(engine)

    async with factory() as session:
        if target in {"reference", "all"}:
            counts = await seed_reference_data(session)
            await session.commit()
            print(f"reference data seeded: {counts}")
        if target in {"demo", "all"}:
            summary = await seed_demo_data(session, settings)
            await session.commit()
            print(f"demo data seeded: {summary}")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "reference")))
