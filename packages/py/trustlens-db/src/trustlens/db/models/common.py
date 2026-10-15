"""Common models. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from sqlalchemy import (
    Enum as SAEnum,
)


def pg_enum(enum_cls: type, name: str) -> SAEnum:
    """Native PostgreSQL ENUM.

    `values_callable` stores the enum *values*, not the Python member names,
    so the database column reads the same as the API payload.
    """
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda x: [member.value for member in x],
        native_enum=True,
        create_type=False,
    )
