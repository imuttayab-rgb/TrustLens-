"""Authorize job ownership using trusted enqueue scope, independently of HTTP/UI.

A random job ID is an identifier, never a capability. Legacy jobs without an
owner scope fail closed. The database and queue paths use this same guard.
"""

from typing import Any
from uuid import UUID
from trustlens.core.domain.enums import UserRole
from trustlens.core.domain.errors import EntityNotFound


async def authorize_job(
    job_id: str, name: str, payload: dict[str, Any], actor: Any, uow: Any
) -> None:
    """Ordinary users can poll only their own known job types; staff need both gates."""
    if actor.has_any_role(UserRole.ADMIN, UserRole.REVIEWER) and actor.has_permission("job:read"):
        return
    seller_id = None
    try:
        if name in {"identity.verify", "scoring.recompute_trust_score"}:
            seller_id = UUID(str(payload.get("seller_id", "")))
        elif name == "listings.analyse_listing":
            listing = await uow.listings.get(UUID(str(payload.get("listing_id", ""))))
            seller_id = listing.seller_id if listing else None
        if seller_id is not None:
            seller = await uow.sellers.get(seller_id)
            if seller is not None and seller.user_id == actor.user_id:
                return
    except (ValueError, TypeError):
        pass
    raise EntityNotFound("job", job_id)


def public_job_result(name: str, result: Any) -> dict[str, Any] | None:
    """Project bounded, typed job outcomes; never expose arbitrary worker dictionaries."""
    if not isinstance(result, dict):
        return None
    safe: dict[str, Any] = {}
    if name == "identity.verify":
        if isinstance(result.get("decision"), str) and result["decision"] in {
            "NOT_STARTED",
            "PENDING",
            "PROCESSING",
            "VERIFIED",
            "REJECTED",
            "EXPIRED",
            "FAILED",
        }:
            safe["decision"] = result["decision"]
        if isinstance(result.get("requires_manual_review"), bool):
            safe["requires_manual_review"] = result["requires_manual_review"]
    elif name == "scoring.recompute_trust_score":
        if type(result.get("score")) in (int, float) and 0 <= result["score"] <= 100:
            safe["score"] = result["score"]
        if result.get("risk_level") in {"LOW", "MEDIUM", "HIGH"}:
            safe["risk_level"] = result["risk_level"]
    elif name == "listings.analyse_listing":
        if type(result.get("risk_score")) in (int, float) and 0 <= result["risk_score"] <= 100:
            safe["risk_score"] = result["risk_score"]
    return safe or None
