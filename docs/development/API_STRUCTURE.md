# API structure and extension guide

API routes are grouped under `/api/v1` for application clients and `/public/v1` for the existing partner contract. `main.py` wires routers/middleware and asserts that non-public routes have access guards. Feature modules organize implementation; they do not create new URL prefixes by accident.

## Add a capability

1. Define domain rules/errors and framework-free use cases under `trustlens-core` where reusable business behavior belongs.
2. Put application orchestration under `trustlens_api/modules/<feature>/service.py`. Use injected container/unit-of-work dependencies; avoid starting network clients or querying a database during module import.
3. Put persistent queries into the appropriate `trustlens/db/repositories/<domain>.py` module. Add models to `models/<domain>.py` and explicit package exports so Alembic sees them. Add an additive migration for schema changes.
4. Define input/output models in `api/v1/schemas/<feature>.py`. Validate limits, identifiers and supported values at the boundary.
5. Add a small router in `api/v1/routers/<feature>.py`, register it in `router.py`, and reuse auth dependencies. Check resource ownership in the service as well as endpoint authentication.
6. Return the existing `envelope` format. Raise typed domain errors; let `exceptions/handlers.py` normalize them. Never return success with an embedded hidden failure.
7. Add queries/mutations to the frontend feature. JSON requests use `packages/api-client` transport. UI renders the controller's state and recoverable errors.
8. Test public contracts and denial cases, then regenerate the OpenAPI client if wire schemas changed.

## Reliability and scale

Use bounded pagination with deterministic ordering. Use idempotency keys for retryable creation; retain database constraints as the final arbiter. Acquire locks in a consistent order (messaging locks listing before conversation). Keep external I/O outside unnecessarily long transactions. Set network timeouts; retry only operations whose semantics support retries. Never retry arbitrary mutations silently.

Run migrations as a single release job. API workers share PostgreSQL/Redis state, not process-local ownership maps. Move expensive processing to the worker through the established queue. Keep private messages and media behind participant-scoped routes, with private/no-store responses. Persist audit events for decisions that need investigation, without logging raw secrets or full sensitive request bodies.

## Existing seams

Messaging and calling are separated into feature modules; profiles, photos and Google authentication use the same layout. Core marketplace domains already use ports/repositories/use cases. Some older read-only routers still assemble projections directly; this release does not claim that every legacy endpoint has been rewritten. Prefer focused extraction when changing those endpoints, backed by behavior tests.
