"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from trustlens.shared.config.settings import Settings, get_settings
from trustlens.shared.logging import configure_logging, get_logger
from trustlens.shared.telemetry import init_error_reporting
from trustlens_api.api.public.v1.router import public_v1
from trustlens_api.api.v1.router import api_v1, health
from trustlens_api.container import build_container, close_container
from trustlens_api.exceptions.handlers import register_exception_handlers
from trustlens_api.middleware import install_middleware

log = get_logger(__name__)

DESCRIPTION = """\
**TrustLens** verifies whether an online marketplace seller is genuine or fake
and publishes a single **explainable Trust Score (0-100)** with a risk level
and the reasons behind it.

Two APIs live here:

| | Base path | Auth | Contains PII |
|---|---|---|---|
| Internal | `/api/v1` | JWT bearer + httpOnly refresh cookie | Yes (own data only) |
| Public | `/public/v1` | API key (`Authorization: Bearer tl_live_...`) | **No** |

### How the score works

AI components (EasyOCR, DeepFace, an LLM, a trained classifier) produce
*evidence with a confidence value*. A versioned, deterministic rule set turns
that evidence into points. The full per-signal breakdown is stored with every
score, so an explanation never requires recomputation - and the same inputs
always produce the same score.

Errors follow **RFC 9457** (`application/problem+json`) and always carry a
stable `code` plus the `requestId` to quote in a support request.
"""

TAGS = [
    {"name": "Authentication", "description": "Registration, sign-in, session rotation."},
    {"name": "Me", "description": "The current user and their seller profile."},
    {"name": "Verification", "description": "Identity, phone, email and device checks."},
    {"name": "Trust Score", "description": "Scores, breakdowns, history and improvements."},
    {"name": "Jobs", "description": "Poll background work such as OCR and face matching."},
    {"name": "Public API", "description": "Partner-facing, API-key authenticated, PII-free."},
    {"name": "Public Page", "description": "Anonymous buyer-facing reads. No key, no PII."},
    {"name": "Health", "description": "Liveness and readiness probes."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    configure_logging(
        level=settings.log_level,
        fmt=settings.log_format,
        service=settings.observability.otel_service_name,
        version=settings.app_version,
        env=settings.env.value,
    )
    log.info(
        "starting",
        env=settings.env.value,
        version=settings.app_version,
        fake_ai=settings.ai.use_fake_ai,
    )

    init_error_reporting(
        settings.observability,
        environment=settings.env.value,
        release=settings.app_version,
        component="api",
    )

    app.state.container = await build_container(settings)
    _assert_routes_are_guarded(app)

    log.info("started", routes=len(app.routes))
    try:
        yield
    finally:
        log.info("shutting_down")
        await close_container(app.state.container)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title=f"{settings.app_name} API",
        description=DESCRIPTION,
        version=settings.app_version,
        openapi_tags=TAGS,
        lifespan=lifespan,
        # Swagger for the INTERNAL API is closed in production. The public API
        # reference is published separately.
        docs_url="/docs" if settings.expose_docs else None,
        redoc_url="/redoc" if settings.expose_docs else None,
        openapi_url="/openapi.json" if settings.expose_docs else None,
        # Errors are problem+json, not the FastAPI default, so the default
        # response class is set explicitly at the handler layer.
        swagger_ui_parameters={"persistAuthorization": True},
    )
    app.state.settings = settings

    install_middleware(app, settings)
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(api_v1, prefix="/api/v1")
    app.include_router(public_v1, prefix="/public/v1")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/docs" if settings.expose_docs else "/health/live")

    return app


#: Routes that are legitimately public. Anything else without an auth
#: dependency is a bug, and the startup assertion below catches it.
_PUBLIC_ROUTES = {
    "/",
    "/health/live",
    "/health/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/docs/oauth2-redirect",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/public/v1/status",
    "/health/worker",
    # The buyer-facing score read (P0-12). Anonymous by design - it is a page
    # a buyer opens from a chat link, not an integration. PII-free by
    # construction (it returns the partner API's projection) and IP rate
    # limited in the handler.
    "/api/v1/public/sellers/{seller_ref}/trust-score",
    # The public listing catalog (browse/search) and the "view this listing"
    # page it opens into. Same anonymous-by-design reasoning: a buyer opens
    # these directly, and both are IP rate limited in the handler.
    "/api/v1/public/listings",
    "/api/v1/public/listings/{listing_id}",
}


def _assert_routes_are_guarded(app: FastAPI) -> None:
    """Deny by default, verified at startup.

    Walks the router tree and fails the boot if a non-public route has no
    authentication dependency. A forgotten `Depends(get_current_actor)` is one
    of the easiest and most damaging mistakes to make in a codebase this size,
    and review does not reliably catch it.

    Routes are read through `iter_route_contexts` rather than by iterating
    `app.routes` directly. Since FastAPI 0.141 an `include_router` call leaves
    a deferred `_IncludedRouter` placeholder in `app.routes` instead of the
    routes themselves, so the obvious loop walks 8 placeholders, finds one
    real route, and reports everything as fine - which is exactly what this
    check did, silently, until P0-12 added a route that depends on it.
    """
    from fastapi.routing import iter_route_contexts

    auth_markers = (
        "get_current_actor",
        "get_optional_actor",
        "get_api_client",
        "require_permissions",
        "require_roles",
        "require_scope",
        "get_current_seller",
    )

    unguarded: list[str] = []
    checked = 0
    for context in iter_route_contexts(app.routes):
        path = getattr(context, "path", "")
        dependant = getattr(context, "dependant", None)
        if dependant is None or not path:
            continue
        checked += 1
        if path in _PUBLIC_ROUTES:
            continue
        dependency_names = {getattr(dep.call, "__name__", "") for dep in dependant.dependencies}
        dependency_names |= {
            getattr(sub.call, "__name__", "")
            for dep in dependant.dependencies
            for sub in dep.dependencies
        }
        flattened = " ".join(dependency_names) + " " + str(dependant.dependencies)
        if not any(marker in flattened for marker in auth_markers):
            methods = getattr(context, "methods", None) or ["GET"]
            unguarded.append(f"{next(iter(methods))} {path}")

    log.info("route_guard_checked", routes=checked, unguarded=len(unguarded))
    if unguarded:
        log.error("routes_without_explicit_auth_dependency", routes=unguarded)
        raise RuntimeError(
            "Routes without an authentication dependency: "
            + ", ".join(sorted(unguarded))
            + ". Add an auth dependency, or add the path to _PUBLIC_ROUTES if it is "
            "deliberately anonymous."
        )


app = create_app()

__all__ = ["app", "create_app"]
