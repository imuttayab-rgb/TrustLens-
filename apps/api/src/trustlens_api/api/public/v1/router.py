"""Aggregates every /public/v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from trustlens_api.api.public.v1.routers import trust_scores

public_v1 = APIRouter()
public_v1.include_router(trust_scores.router)

__all__ = ["public_v1"]
