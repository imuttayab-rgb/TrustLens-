# 03 — Backend Architecture

Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · Alembic · Pydantic v2 · ARQ · Redis · PostgreSQL

## 1. Layering

Clean Architecture with four layers. The **Dependency Rule** is absolute: source dependencies point
inward only.

| Layer                          | Lives in                                  | Knows about                   | Never knows about         |
| ------------------------------ | ----------------------------------------- | ----------------------------- | ------------------------- |
| **Domain**                     | `packages/py/trustlens-core/domain/`      | Nothing but Python + Pydantic | HTTP, SQL, Redis, vendors |
| **Application** (use cases)    | `packages/py/trustlens-core/application/` | Domain + ports                | Concrete adapters         |
| **Adapters**                   | `packages/py/trustlens-{db,ai,shared}/`   | Domain ports + vendor SDKs    | Each other, or apps       |
| **Presentation / composition** | `apps/api`, `apps/worker`                 | Everything (it wires them)    | —                         |

```
HTTP request
   ↓
Router (apps/api/api/v1/routers/…)          ← routing, status codes, OpenAPI metadata
   ↓  Pydantic request DTO
Dependency (…/api/deps/…)                    ← auth, RBAC, tenant/actor resolution, UoW
   ↓
Use case (trustlens-core/application/…)      ← orchestration, transaction boundary, events
   ↓  Ports (Protocols)
Repository / Gateway impls (trustlens-db, trustlens-ai, trustlens-shared)
   ↓
PostgreSQL · Redis · Object storage · OpenAI/Claude · OpenCV/EasyOCR/DeepFace · SMS · Email · IP intel
```

> **WHY use cases instead of "fat services":** a class named `SellerService` accretes every seller-related
> method until it is 900 lines with 11 constructor dependencies — a Single Responsibility violation that
> is impossible to test in isolation. One class per use case (`SubmitIdentityDocuments`,
> `ComputeTrustScore`, `SubmitAppeal`) has exactly the dependencies it needs, is named after a business
> action, and is trivially testable with fakes. The tradeoff is more files; in a codebase this size that is
> a good trade.

## 2. `packages/py/trustlens-core` — the domain

```
trustlens-core/
├── pyproject.toml
└── src/trustlens/core/
    ├── domain/
    │   ├── entities/
    │   │   ├── user.py                 # User, Role, Permission
    │   │   ├── seller.py               # SellerProfile
    │   │   ├── identity.py             # IdentityDocument, IdentityVerification
    │   │   ├── contact.py              # PhoneNumber, EmailAddress
    │   │   ├── device.py               # Device, DeviceLink
    │   │   ├── network.py              # IpAddress, AccessEvent
    │   │   ├── listing.py              # Listing, ListingImage, ListingAnalysis
    │   │   ├── trust_score.py          # TrustScore, TrustScoreSignal
    │   │   ├── appeal.py               # Appeal, AppealMessage
    │   │   └── api_client.py           # ApiClient, ApiKey
    │   ├── value_objects/
    │   │   ├── email.py                # Email — normalises + validates at construction
    │   │   ├── phone.py                # PhoneE164
    │   │   ├── cnic.py                 # CnicNumber — 13-digit checksum/format rules
    │   │   ├── money.py                # Money(amount, currency)
    │   │   ├── score.py                # Score — clamped 0..100, exposes .risk_level
    │   │   ├── confidence.py           # Confidence — 0.0..1.0
    │   │   └── fingerprint.py          # DeviceFingerprint
    │   ├── enums/
    │   │   ├── risk_level.py           # LOW | MEDIUM | HIGH
    │   │   ├── signal.py               # SignalCode, SignalCategory, SignalStatus
    │   │   ├── verification.py         # VerificationStatus, DocumentType
    │   │   ├── appeal.py               # AppealStatus, AppealDecision
    │   │   ├── listing.py              # ListingStatus, ListingSource
    │   │   └── user.py                 # UserRole, AccountStatus
    │   ├── events/
    │   │   ├── base.py                 # DomainEvent
    │   │   ├── identity_events.py      # IdentityVerified, IdentityRejected
    │   │   ├── contact_events.py       # PhoneVerified, EmailVerified
    │   │   ├── listing_events.py       # ListingAnalysed
    │   │   └── score_events.py         # TrustScoreComputed, TrustScoreOverridden
    │   ├── errors/
    │   │   ├── base.py                 # DomainError (code, message, details)
    │   │   ├── auth.py                 # InvalidCredentials, TokenReused, …
    │   │   ├── verification.py         # OtpExpired, TooManyAttempts, FaceMismatch, …
    │   │   └── scoring.py              # NoActiveScoringModel, InsufficientSignals
    │   ├── policies/                   # pure business rules, heavily unit-tested
    │   │   ├── scoring_policy.py       # weights → points, hard caps, normalisation
    │   │   ├── risk_band_policy.py     # score → RiskLevel (A1 thresholds)
    │   │   ├── freshness_policy.py     # when is a score stale? (A14)
    │   │   ├── device_linkage_policy.py# how many accounts per device is suspicious
    │   │   └── appeal_policy.py        # who may appeal, how often, within what window
    │   └── ports/                      # Protocol interfaces — the seams of the system
    │       ├── repositories.py         # UserRepository, SellerRepository, TrustScoreRepository, …
    │       ├── unit_of_work.py         # UnitOfWork (async context manager)
    │       ├── ocr.py                  # OcrEngine.extract(image) -> OcrResult
    │       ├── face_match.py           # FaceMatcher.compare(a, b) -> FaceMatchResult
    │       ├── llm.py                  # LlmAnalyzer.analyze_listing(...) -> ListingAnalysis
    │       ├── classifier.py           # ScamClassifier.predict(features) -> ClassifierResult
    │       ├── ip_intelligence.py      # IpIntelligence.lookup(ip) -> IpReputation
    │       ├── storage.py              # ObjectStorage.put/get/presign/delete
    │       ├── cache.py                # Cache.get/set/delete/incr
    │       ├── queue.py                # JobQueue.enqueue(name, **kwargs)
    │       ├── notifications.py        # EmailSender, SmsSender
    │       ├── clock.py                # Clock.now() — never call datetime.utcnow() in domain code
    │       └── id_generator.py         # IdGenerator.new() -> UUID
    └── application/
        ├── use_cases/
        │   ├── auth/                   # RegisterUser, LoginUser, RefreshSession, …
        │   ├── verification/           # SubmitIdentityDocuments, RequestPhoneOtp, …
        │   ├── listings/               # CreateListing, AnalyseListing, …
        │   ├── scoring/                # ComputeTrustScore, GetCurrentTrustScore, OverrideTrustScore
        │   ├── appeals/                # SubmitAppeal, AssignAppeal, ResolveAppeal
        │   ├── admin/                  # UpdateScoringWeights, ActivateScoringModel, …
        │   └── public_api/             # GetPublicTrustScore, RegisterSellerViaApi
        ├── dto/                        # framework-free in/out DTOs per use case
        ├── services/                   # multi-use-case coordination (SignalCollector)
        └── event_bus.py                # in-process dispatch + transactional outbox handoff
```

### Ports and the Clock

`Clock` looks like over-engineering until you test `freshness_policy` ("is this score older than 30 days?").
With a real clock that test is either slow or flaky; with a `FrozenClock` it is one line. Same reasoning
for `IdGenerator` — deterministic IDs make snapshot assertions readable. **Never** call `datetime.now()`,
`uuid4()`, or `random` inside `trustlens-core`; a lint rule enforces it.

### Use case shape

Every use case is a class with `__init__(self, *deps)` and a single `async def execute(self, cmd) -> Result`.
It owns the transaction boundary via `UnitOfWork`, and it publishes domain events **inside** that
transaction through the outbox, so an event can never be emitted for a rolled-back change.

```
class ComputeTrustScore:
    def __init__(self, uow, signal_collector, scoring_policy_factory, cache, clock, events): ...
    async def execute(self, cmd: ComputeTrustScoreCommand) -> TrustScoreResult:
        async with self.uow:
            model   = await self.uow.scoring_models.get_active()
            signals = await self.signal_collector.collect(cmd.seller_id)
            score   = self.scoring_policy_factory.for_model(model).evaluate(signals)
            saved   = await self.uow.trust_scores.replace_current(score)
            await self.events.publish(TrustScoreComputed(...))
            await self.uow.commit()
        await self.cache.delete(f"score:{cmd.seller_id}:*")
        return TrustScoreResult.from_entity(saved)
```

Note the cache invalidation is **after** commit — invalidating before commit can repopulate the cache from
a transaction that then rolls back.

## 3. `apps/api` — FastAPI presentation layer

```
apps/api/
├── pyproject.toml
├── Dockerfile
├── alembic.ini -> ../../database/alembic.ini     # symlink; migrations live in database/
└── src/trustlens_api/
    ├── main.py                     # create_app(): routers, middleware, lifespan, OpenAPI
    ├── container.py                # DI container: builds adapters, wires ports → use cases
    ├── core/
    │   ├── settings.py             # pydantic-settings; fail-fast on missing/invalid env
    │   ├── security.py             # password hashing (argon2id), JWT encode/decode, key hashing
    │   ├── logging.py              # structlog JSON config + PII redaction processor
    │   ├── openapi.py              # tags, servers, security schemes, examples
    │   └── constants.py
    ├── middleware/
    │   ├── request_context.py      # request_id, trace_id, actor into contextvars
    │   ├── logging_middleware.py   # structured access log with duration + status
    │   ├── security_headers.py     # HSTS, CSP, X-Content-Type-Options, Referrer-Policy
    │   ├── cors.py                 # strict allowlist from settings
    │   ├── rate_limit.py           # Redis token bucket, per-identity policies
    │   ├── idempotency.py          # Idempotency-Key replay protection for unsafe methods
    │   └── body_size_limit.py      # reject oversized uploads before they are buffered
    ├── api/
    │   ├── v1/                                 # internal API — JWT
    │   │   ├── router.py                       # aggregates all v1 routers
    │   │   ├── routers/
    │   │   │   ├── auth.py         health.py   me.py
    │   │   │   ├── sellers.py      verification_identity.py
    │   │   │   ├── verification_phone.py       verification_email.py
    │   │   │   ├── verification_device.py      listings.py
    │   │   │   ├── trust_scores.py jobs.py     files.py
    │   │   │   ├── appeals.py      notifications.py
    │   │   │   └── admin/          # users.py, reviews.py, scoring_models.py,
    │   │   │                       # api_clients.py, appeals.py, audit_logs.py, metrics.py
    │   │   └── schemas/            # Pydantic request/response DTOs, one module per resource
    │   │       ├── common.py       # Envelope, PageMeta, CursorMeta, ProblemDetail
    │   │       ├── auth.py  seller.py  identity.py  contact.py  listing.py
    │   │       ├── trust_score.py  appeal.py  admin.py  job.py
    │   ├── public/v1/                          # partner API — API key
    │   │   ├── router.py
    │   │   ├── routers/ trust_scores.py  sellers.py  webhooks.py  status.py
    │   │   └── schemas/ public_score.py        # deliberately PII-free
    │   └── deps/
    │       ├── auth.py             # get_current_user, get_optional_user
    │       ├── rbac.py             # require_roles(...), require_permissions(...)
    │       ├── api_key.py          # get_api_client, require_scope(...)
    │       ├── uow.py              # request-scoped UnitOfWork / DB session
    │       ├── use_cases.py        # one provider per use case, resolved from container
    │       ├── pagination.py       # PageParams / CursorParams
    │       └── request_meta.py     # client IP (trusted proxy aware), UA, device header
    ├── exceptions/
    │   ├── handlers.py             # DomainError / ValidationError / HTTPException / Exception
    │   └── mapping.py              # DomainError code → HTTP status (single table)
    └── openapi_export.py           # dumps openapi.json for the TS client generator
```

### Middleware order (outermost first — order is a correctness concern)

1. `RequestContextMiddleware` — assign `request_id` first so _everything_ downstream can log it
2. `SecurityHeadersMiddleware`
3. `CORSMiddleware`
4. `BodySizeLimitMiddleware` — reject before buffering
5. `LoggingMiddleware` — wraps the rest so it can time the full handler
6. `RateLimitMiddleware` — after identity resolution, before expensive work
7. `IdempotencyMiddleware` — innermost; only applies to unsafe methods carrying `Idempotency-Key`

### Guards → FastAPI dependencies

FastAPI has no NestJS-style "guards"; the equivalent is a dependency that raises. Composable and typed:

```
@router.post("/admin/scoring-models/{id}/activate",
             dependencies=[Depends(require_permissions("scoring_model:activate"))])
```

`require_permissions` reads permissions from the JWT claims, falls back to a Redis-cached DB lookup on a
version mismatch (so a revoked role takes effect within seconds instead of one token lifetime), and
raises `ForbiddenError` on failure. Details in [07](07-authentication-authorization.md).

### Interceptors → middleware + dependency wrappers

The cross-cutting behaviours an "interceptor" would provide are mapped explicitly:

| Interceptor concern   | Implementation                                                                 |
| --------------------- | ------------------------------------------------------------------------------ |
| Response envelope     | `ResponseModel` + a `response_model` wrapper generic `Envelope[T]`             |
| Timing / access log   | `LoggingMiddleware`                                                            |
| Exception translation | Global exception handlers (`exceptions/handlers.py`)                           |
| Serialization         | Pydantic `model_config` with `from_attributes=True`, camelCase alias generator |
| Caching               | Explicit in the use case — never a magic decorator that hides invalidation     |
| Audit trail           | `AuditingUnitOfWork` decorator that writes `audit_logs` rows on commit         |

> **WHY no cache decorator:** implicit caching is the most common source of "why is this data stale" bugs.
> Cache reads and invalidations are written out in the use case where the reader can see both halves.

### Exception handling

One mapping table, no scattered `HTTPException`s in routers:

| Domain error                                                             | HTTP | `type` (RFC 9457)                                                                                     |
| ------------------------------------------------------------------------ | ---- | ----------------------------------------------------------------------------------------------------- |
| `ValidationError` (Pydantic)                                             | 422  | `/errors/validation-failed`                                                                           |
| `InvalidCredentials`                                                     | 401  | `/errors/invalid-credentials`                                                                         |
| `TokenExpired` / `TokenReused`                                           | 401  | `/errors/token-invalid`                                                                               |
| `PermissionDenied`                                                       | 403  | `/errors/permission-denied`                                                                           |
| `EntityNotFound`                                                         | 404  | `/errors/not-found`                                                                                   |
| `ConflictError` (duplicate email/phone)                                  | 409  | `/errors/conflict`                                                                                    |
| `UnprocessableStateError` (e.g. appeal on a score that no longer exists) | 422  | `/errors/invalid-state`                                                                               |
| `RateLimitExceeded`                                                      | 429  | `/errors/rate-limited`                                                                                |
| `ExternalServiceError`                                                   | 502  | `/errors/upstream-failed`                                                                             |
| `ServiceUnavailable`                                                     | 503  | `/errors/unavailable`                                                                                 |
| Anything else                                                            | 500  | `/errors/internal` — **message replaced with a generic string**, real detail logged with `request_id` |

Rule: internal exception text is never returned to a client. The response carries a `request_id` the
user can quote; the log carries the stack trace.

### Logging

`structlog` → JSON to stdout (Railway aggregates stdout).

Every line carries: `timestamp, level, event, request_id, trace_id, actor_id, actor_type, route, method,
status, duration_ms, env, version`.

A **redaction processor** runs last in the chain and drops or masks keys matching
`password, token, refresh_token, authorization, api_key, cnic, cnic_number, otp, selfie_url, dob,
face_embedding`. Redaction lives in the processor rather than at call sites because call sites are where
people forget.

Log levels: `DEBUG` local only · `INFO` state changes and access logs · `WARNING` degraded paths
(fallback adapter used, retry) · `ERROR` failed operations · `CRITICAL` data-integrity or security events
(refresh-token reuse, API key brute force) which also raise an alert.

### File uploads

Uploads are the highest-risk surface in this system (CNIC images and selfies).

1. Client requests `POST /api/v1/files/upload-intent` → server validates purpose and quota, returns a
   **presigned PUT URL** + a `file_id`.
2. Client uploads directly to object storage (the API never proxies image bytes → no memory spikes).
3. Client calls `POST /api/v1/verification/identity` referencing `file_id`s.
4. Server verifies: object exists, size ≤ limit, **magic-byte sniffing** (not the client's `Content-Type`,
   not the extension), dimensions within bounds, EXIF stripped, re-encoded to a normalised JPEG/PNG.
5. `files` row records checksum, mime, size, owner, purpose, and `scan_status`.

Constraints: max 10 MB per image, JPEG/PNG/WEBP only, private bucket, no public URLs ever — reads go
through short-lived (5 min) presigned GETs, authorised per request. Full rationale in
[15 §6](15-security.md).

## 4. `apps/worker` — background processing

```
apps/worker/src/trustlens_worker/
├── main.py                     # ARQ WorkerSettings: functions, cron, redis, concurrency
├── container.py                # same wiring as the API, plus ML adapters
├── jobs/
│   ├── identity.py             # run_cnic_ocr, run_face_match, finalize_identity
│   ├── contact.py              # send_otp_sms, send_verification_email, check_email_domain
│   ├── network.py              # enrich_ip, recompute_device_links
│   ├── listings.py             # analyse_listing_llm, classify_listing, hash_listing_images
│   ├── scoring.py              # recompute_trust_score, bulk_recompute_for_model
│   ├── webhooks.py             # deliver_webhook (with signature + retry)
│   ├── notifications.py        # send_notification
│   └── maintenance.py          # purge_expired_media, rotate_logs, refresh_disposable_domains
├── cron.py                     # scheduled: nightly rescore of stale sellers, cleanup, metric rollups
└── middleware/
    ├── job_context.py          # propagate request_id/trace_id from the enqueuing request
    └── retry_policy.py         # per-job max_tries, backoff, dead-letter routing
```

Job design rules:

- **Idempotent.** Every job re-runnable with the same args and the same end state. Retries are guaranteed
  to happen; jobs that aren't idempotent corrupt data.
- **Small payloads.** Enqueue IDs, never image bytes or model outputs.
- **Bounded.** `max_tries` and `job_timeout` on every job. Exhausted jobs land in a `dead_letter` list
  and are surfaced in the admin panel — silent job loss is unacceptable when the outcome affects a score.
- **Traced.** `request_id` propagates from the originating HTTP request into the job's log context, so a
  seller-reported problem can be followed end to end.

The scoring job is the only writer of `trust_scores`, which makes concurrency reasoning trivial: a
per-seller **Redis lock** plus a queue-level dedup key collapses a burst of signal changes into one
recomputation.

## 5. `packages/py/trustlens-db` — persistence adapter

```
src/trustlens/db/
├── base.py            # DeclarativeBase, naming convention for constraints/indexes
├── session.py         # async engine + sessionmaker, pool config
├── unit_of_work.py    # SqlAlchemyUnitOfWork implementing the port
├── mixins.py          # TimestampMixin, SoftDeleteMixin, AuditMixin, VersionedMixin
├── types.py           # EncryptedString, CIText, PhoneHash, custom TypeDecorators
├── models/            # one module per aggregate; mirrors docs/05
├── repositories/      # SqlAlchemy*Repository — each implements a core port
├── queries/           # hand-written read models for dashboards/analytics (no ORM overhead)
└── seed/              # idempotent reference-data seeders (roles, permissions, signals, model v1)
```

Repositories return **domain entities**, never ORM models — mapping happens at the repository edge. That
is what keeps SQLAlchemy out of `trustlens-core`, and it is what makes the in-memory fake repositories in
tests behaviourally equivalent.

Read-heavy admin screens bypass repositories and use `queries/` (explicit SQL returning DTOs). Forcing
every read through aggregate repositories is the classic cause of N+1 death in admin panels; CQRS-lite
avoids it without adopting full CQRS.

## 6. `packages/py/trustlens-ai` — AI adapter

```
src/trustlens/ai/
├── ocr/
│   ├── easyocr_engine.py       # implements OcrEngine
│   ├── preprocessing.py        # OpenCV: deskew, denoise, adaptive threshold, perspective correct
│   └── cnic_parser.py          # maps raw OCR tokens → CnicFields (name, number, DOB, expiry)
├── face/
│   ├── deepface_matcher.py     # implements FaceMatcher
│   ├── detection.py            # face crop from CNIC photo region + selfie
│   └── quality.py              # blur/lighting/pose gates — reject bad input before comparing
├── llm/
│   ├── base.py                 # shared prompt/response contract
│   ├── openai_analyzer.py      # implements LlmAnalyzer
│   ├── anthropic_analyzer.py   # implements LlmAnalyzer
│   ├── prompts/                # versioned prompt templates (prompt_version is stored per analysis)
│   └── schemas.py              # strict structured output schema for listing analysis
├── classifier/
│   ├── scam_classifier.py      # implements ScamClassifier
│   ├── features.py             # feature extraction shared with apps/ml training
│   └── registry.py             # loads a versioned model artifact from object storage
└── resilience.py               # timeout, retry with jitter, circuit breaker, cost/token accounting
```

Two adapters implement `LlmAnalyzer` (OpenAI and Claude — the proposal says "OpenAI / Claude API"). The
active provider is an env var; both are exercised in CI against recorded fixtures. This is Liskov
substitution used deliberately: the use case cannot tell which one it got.

`features.py` is shared between training (`apps/ml`) and inference (`trustlens-ai`) on purpose —
train/serve feature skew is the single most common cause of a classifier that scores well offline and
badly in production.

## 7. `packages/py/trustlens-shared` — infrastructure adapter

```
src/trustlens/shared/
├── config/            # BaseSettings, env loading, secret resolution, per-env profiles
├── logging/           # structlog processors, redaction, correlation ids
├── storage/           # S3Storage (boto3) + LocalStorage (dev) implementing ObjectStorage
├── cache/             # RedisCache implementing Cache; key builders; namespaced TTLs
├── queue/             # ArqJobQueue implementing JobQueue (enqueue by name)
├── notifications/     # SmtpEmailSender, ResendEmailSender, TwilioSmsSender, ConsoleSender (dev)
├── ip/                # HttpIpIntelligence + OfflineAsnIpIntelligence (fallback chain)
├── crypto/            # envelope encryption (AES-256-GCM), hashing (argon2id, HMAC-SHA256), tokens
├── clock.py           # SystemClock
├── ids.py             # Uuid7Generator — time-ordered UUIDs for index locality
└── telemetry/         # OpenTelemetry tracing + Prometheus metrics helpers
```

> **WHY UUIDv7 over UUIDv4:** random UUID primary keys scatter B-tree inserts across the index, which
> hurts write throughput and cache locality on the high-volume tables (`access_events`,
> `api_request_logs`). UUIDv7 is time-ordered, so it keeps insert locality like a bigserial while staying
> globally unique and non-enumerable in URLs.

## 8. Configuration management

`pydantic-settings` with a typed `Settings` class per app, composed from shared setting groups
(`DatabaseSettings`, `RedisSettings`, `AiSettings`, `StorageSettings`, `SecuritySettings`).

Rules:

1. **Fail fast.** The app refuses to start on a missing or malformed variable — never `os.getenv(...) or ""`.
2. **No defaults for secrets.** A default `JWT_SECRET` is how a development key reaches production.
3. **`Settings` is constructed once** at startup and injected; nothing reads `os.environ` at call time.
4. **Environment parity.** The same `Settings` class in all environments; only values differ.
5. Production additionally asserts: `DEBUG is False`, `ENV == "production"`, secrets ≥ 32 bytes,
   CORS origins non-wildcard, `DATABASE_URL` uses TLS.

Full variable list: [12 — Environment Variables](12-environment-variables.md).

## 9. How SOLID shows up here (concretely)

| Principle                 | Where                                                                                                                                    |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **S**ingle responsibility | One class per use case; policies separated from entities; repositories separated from query models                                       |
| **O**pen/closed           | New signal = new `SignalCollector` + a `signal_definitions` row + a weight. The scoring policy is not modified                           |
| **L**iskov                | `OpenAiAnalyzer` and `AnthropicAnalyzer` are interchangeable behind `LlmAnalyzer`; both pass the same contract test suite                |
| **I**nterface segregation | Narrow ports (`OcrEngine` has one method) instead of one `AiService` god-interface; repositories are per-aggregate, not one `Repository` |
| **D**ependency inversion  | `trustlens-core` defines the ports; adapters depend on core, never the reverse — enforced by `import-linter` in CI                       |
