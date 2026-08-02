"""Alembic environment.

Metadata is imported from packages/py/trustlens-db, so models and migrations
have a single source of truth even though migrations live here (see
docs/10 section 4 for why they are separated).
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[2]
for package in ("trustlens-core", "trustlens-shared", "trustlens-db"):
    sys.path.insert(0, str(ROOT / "packages" / "py" / package / "src"))

from trustlens.db import models  # noqa: E402,F401  (registers every table)
from trustlens.db.base import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic runs as a bare script, so nothing has loaded the project's .env yet -
# unlike the app, which goes through pydantic-settings. Without this, `make
# migrate` fails on a correctly configured checkout. A real environment
# variable still wins, so CI and production are unaffected.
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except ModuleNotFoundError:  # pragma: no cover - dotenv ships with the app deps
    pass

url = os.environ.get("DATABASE_URL_SYNC")
if not url:
    raise SystemExit(
        "DATABASE_URL_SYNC is not set. Alembic needs a SYNC driver "
        "(postgresql+psycopg://...), not the asyncpg URL the app uses."
    )
config.set_main_option("sqlalchemy.url", url)

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    # Monthly partitions are created by a cron job, not by Alembic; without
    # this filter autogenerate would propose dropping every one of them.
    return not (type_ == "table" and "_y20" in str(name))


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
            # One transaction for the whole migration: a half-applied schema
            # change is far worse than a failed deploy.
            transaction_per_migration=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
