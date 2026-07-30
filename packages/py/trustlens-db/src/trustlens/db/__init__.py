"""TrustLens persistence adapter.

Deliberately minimal: importing this package must NOT pull in application
settings. Alembic imports the metadata from here, and a migration that cannot
run without a fully-valid .env is a migration you cannot run in a recovery
situation.

Import the session helpers explicitly where you need them:

    from trustlens.db.session import create_engine, create_session_factory
    from trustlens.db.unit_of_work import SqlAlchemyUnitOfWork
"""

from trustlens.db.base import Base

__all__ = ["Base"]
