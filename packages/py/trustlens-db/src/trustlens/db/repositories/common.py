"""Common repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from typing import Any
from sqlalchemy import Select


def _alive(stmt: Select[Any], model: Any) -> Select[Any]:
    """Apply the soft-delete filter. Applied centrally, never per call site."""
    return stmt.where(model.deleted_at.is_(None))
