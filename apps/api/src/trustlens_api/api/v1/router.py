"""Aggregates every /api/v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from trustlens_api.api.v1.routers import (
    admin,
    appeals,
    auth,
    health,
    jobs,
    listings,
    me,
    partners,
    trust_scores,
    verification,
)

api_v1 = APIRouter()
api_v1.include_router(auth.router)
api_v1.include_router(admin.router)
api_v1.include_router(appeals.router)
api_v1.include_router(partners.router)
api_v1.include_router(me.router)
api_v1.include_router(verification.router)
api_v1.include_router(listings.router)
api_v1.include_router(trust_scores.router)
api_v1.include_router(jobs.router)

__all__ = ["api_v1", "health"]
