"""The buyer-facing score route, and the guard that lets it stay anonymous (P0-12).

Two things are asserted here, and the second matters more than the first.

The public seller page renders for anonymous buyers, so its route carries no
authentication dependency. That is safe only because `_assert_routes_are_guarded`
refuses to boot an app with an unguarded route that is not on an explicit
allow-list - which makes the allow-list, not a comment, the record of the
decision.

That guard had been inert. Since FastAPI 0.141 `include_router` leaves a
deferred `_IncludedRouter` placeholder in `app.routes` rather than the routes
themselves, so a loop over `app.routes` saw 8 objects, of which exactly one was
a real route. The check reported everything as fine because it was looking at
almost nothing. `test_guard_rejects_an_unguarded_route` is the regression test:
it fails if the guard ever stops seeing the route tree again.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts

from trustlens_api.main import _PUBLIC_ROUTES, _assert_routes_are_guarded, create_app

BUYER_PATH = "/api/v1/public/sellers/{seller_ref}/trust-score"
PARTNER_PATH = "/public/v1/sellers/{seller_ref}/trust-score"

AUTH_MARKERS = (
    "get_current_actor",
    "get_optional_actor",
    "get_api_client",
    "require_permissions",
    "require_roles",
    "require_scope",
    "get_current_seller",
)


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return create_app()


def _context(app: FastAPI, path: str):
    for context in iter_route_contexts(app.routes):
        if getattr(context, "path", "") == path:
            return context
    raise AssertionError(f"route not registered: {path}")


@pytest.mark.api
def test_buyer_route_is_registered(app: FastAPI) -> None:
    """The page 404'd for every seller because this route did not exist."""
    assert BUYER_PATH in app.openapi()["paths"]


@pytest.mark.api
def test_buyer_route_is_anonymous(app: FastAPI) -> None:
    """No auth dependency - a buyer following a chat link has no account."""
    dependant = _context(app, BUYER_PATH).dependant
    names = {getattr(dep.call, "__name__", "") for dep in dependant.dependencies}
    assert not (names & set(AUTH_MARKERS))


@pytest.mark.api
def test_buyer_route_is_on_the_allow_list(app: FastAPI) -> None:
    """Anonymous is a decision, and this is where the decision is recorded."""
    assert BUYER_PATH in _PUBLIC_ROUTES


@pytest.mark.api
def test_partner_route_still_requires_a_key(app: FastAPI) -> None:
    """The fix must not have loosened the partner API on the way past."""
    dependant = _context(app, PARTNER_PATH).dependant
    flattened = str(dependant.dependencies)
    assert "require_scope" in flattened or "get_api_client" in flattened
    assert PARTNER_PATH not in _PUBLIC_ROUTES


@pytest.mark.api
def test_guard_sees_the_whole_route_tree(app: FastAPI) -> None:
    """The bug that made the guard useless: it walked placeholders, not routes.

    Pinned to a floor rather than an exact count so adding a route does not
    fail this, but collapsing back to the deferred-placeholder view does.
    """
    with_dependants = [c for c in iter_route_contexts(app.routes) if getattr(c, "dependant", None)]
    assert len(with_dependants) > 40


@pytest.mark.api
def test_guard_passes_on_the_real_app(app: FastAPI) -> None:
    _assert_routes_are_guarded(app)


@pytest.mark.api
def test_guard_rejects_an_unguarded_route(app: FastAPI) -> None:
    """A guard that never fires is indistinguishable from no guard."""
    from trustlens_api.api.v1.router import api_v1

    unguarded = create_app()

    @api_v1.get("/oops-unguarded-test-route")
    async def _leak() -> dict[str, str]:  # pragma: no cover - never called
        return {"secret": "should never be reachable anonymously"}

    try:
        with pytest.raises(RuntimeError, match="oops-unguarded-test-route"):
            _assert_routes_are_guarded(unguarded)
    finally:
        api_v1.routes[:] = [
            route
            for route in api_v1.routes
            if getattr(route, "path", "") != "/oops-unguarded-test-route"
        ]


@pytest.mark.api
def test_buyer_response_model_carries_no_pii() -> None:
    """The buyer route reuses the partner projection precisely so this holds."""
    from trustlens_api.api.public.v1.schemas.public_score import PublicScoreResponse

    forbidden = ("email", "phone", "cnic", "name", "address", "image", "url", "dob")
    fields = set(PublicScoreResponse.model_fields)
    assert not [f for f in fields if any(word in f.lower() for word in forbidden)]
