# 02 — System Architecture

## 1. Container view

| Container | Technology | Deploys to | Responsibility | Why separate |
|---|---|---|---|---|
| `apps/web` | Next.js 15 (App Router), React 19, Tailwind CSS 4 | **Vercel** | All human UIs: public score lookup, seller portal, admin panel | Proposal mandates Vercel; Vercel is a JS host and cannot run the Python API |
| `apps/api` | FastAPI (Python 3.12), Uvicorn | **Railway** | HTTP surface, authN/authZ, validation, orchestration, job enqueue, cached reads | Must stay small and fast; no ML dependencies |
| `apps/worker` | ARQ (async Redis queue) | **Railway** | OCR, face match, LLM calls, classifier inference, scoring, webhooks, scheduled jobs | Heavy ML deps (torch/tensorflow/opencv) and multi-second runtimes must not sit in the request path |
| `apps/ml` | Python, scikit-learn/PyTorch, DVC-style artifact tracking | Offline / CI | Trains, evaluates and versions the custom scam-listing classifier; publishes model artifacts | Training is a batch concern with a different lifecycle from serving |
| PostgreSQL | Postgres 16 | Railway | System of record | Proposal |
| Redis | Redis 7 | Railway | Job queue, response cache, rate limiting, OTP throttle, idempotency keys | Proposal ("with Redis cache") |
| Object storage | S3-compatible (MinIO locally) | R2 / Supabase / Railway volume | CNIC images, selfies, listing images, model artifacts | Assumption A6 — binaries never belong in Postgres |

> **WHY four apps and not one FastAPI monolith:** a single container would need the ML dependency set,
> making the image ~3 GB, cold starts slow, and every API deploy a risk to the AI pipeline. Splitting the
> *process* while keeping *one codebase and one domain package* gives isolation without microservice
> overhead. `api` and `worker` share `packages/py/*` and the same database — they are two entry points
> into one application, which is the "modular monolith" pattern.

## 2. Monorepo tooling

TrustLens is **polyglot** (TypeScript + Python), which most monorepo tools handle badly. The chosen split:

| Concern | Tool | Rationale |
|---|---|---|
| JS package manager | **pnpm** workspaces | Strict node_modules prevents phantom dependencies; content-addressed store keeps CI fast |
| JS task graph & caching | **Turborepo** | Minimal config, first-class Vercel support, local + remote build cache |
| Python package manager | **uv** workspaces | Single fast resolver for all Python packages; one lockfile; 10–100× faster than pip/Poetry in CI |
| Cross-language entry point | **Makefile** (or Taskfile) at repo root | One vocabulary — `make dev`, `make test`, `make migrate` — regardless of which language a task lands in |
| Git hooks | **Husky** + **lint-staged** | Mandated by the deliverable list; runs Prettier/ESLint on staged JS and Ruff/Black on staged Python |

Rejected: **Nx** (more power than a 2-person FYP needs, steeper learning curve), **Bazel** (correct for
polyglot, wildly disproportionate here), **git submodules / polyrepo** (breaks atomic cross-stack changes —
the single biggest advantage of a monorepo for this project is that changing an API response shape and the
frontend that consumes it is *one commit, one PR, one CI run*).

See [ADR-0001](adr/0001-monorepo-tooling.md).

## 3. Dependency rules (enforced, not aspirational)

```
                     ┌──────────────────────────────┐
                     │  packages/py/trustlens-core  │   pure domain: entities, use cases, PORTS
                     │  (no framework imports)      │   imports: stdlib + pydantic only
                     └───────▲──────▲──────▲────────┘
                             │      │      │
        ┌────────────────────┘      │      └────────────────────┐
┌───────┴────────┐        ┌─────────┴────────┐        ┌─────────┴─────────┐
│ trustlens-db   │        │  trustlens-ai    │        │ trustlens-shared  │
│ SQLAlchemy     │        │  OpenAI/Claude   │        │ config, logging,  │
│ repositories   │        │  OpenCV/EasyOCR  │        │ storage, cache,   │
│ (impl. ports)  │        │  DeepFace, clf   │        │ sms, email, ip    │
└───────▲────────┘        └─────────▲────────┘        └─────────▲─────────┘
        └──────────────┬────────────┴───────────────────────────┘
              ┌────────┴─────────┐          ┌──────────────────┐
              │    apps/api      │          │   apps/worker    │
              │ composition root │          │ composition root │
              └──────────────────┘          └──────────────────┘
```

Rules, checked in CI by `import-linter` (Python) and ESLint `no-restricted-imports` (TS):

1. `trustlens-core` MUST NOT import `sqlalchemy`, `fastapi`, `arq`, `openai`, `anthropic`, `cv2`, or `redis`.
2. Adapter packages MUST NOT import each other (`trustlens-db` never imports `trustlens-ai`).
3. `apps/*` MUST NOT be imported by `packages/*`.
4. `apps/api` MUST NOT import `apps/worker` (it enqueues by job *name*, not by function reference).
5. Frontend features MUST NOT import from another feature's internals — only from `packages/*` or the
   other feature's public `index.ts`.

> **WHY rule 4:** if the API imported worker functions, it would inherit torch and tensorflow through the
> import graph, and the "thin API" decision would silently evaporate. Enqueuing by string name is the
> mechanism that *enforces* the split.

## 4. Runtime flow — seller verification (the critical path)

```
Seller                apps/web            apps/api           Redis          apps/worker         Postgres
  │                      │                   │                 │                 │                 │
  │ upload CNIC + selfie │                   │                 │                 │                 │
  ├─────────────────────►│ POST /v1/verification/identity      │                 │                 │
  │                      ├──────────────────►│                 │                 │                 │
  │                      │                   │ validate (mime, size, magic bytes) │                 │
  │                      │                   ├─ store objects ────────────────────────────────────►│
  │                      │                   │  insert identity_documents (PENDING)                │
  │                      │                   ├─enqueue────────►│                 │                 │
  │                      │◄─202 {job_id}─────┤  identity.verify│                 │                 │
  │◄─"processing"────────┤                   │                 ├────pop─────────►│                 │
  │                      │                   │                 │                 │ OpenCV preprocess
  │                      │                   │                 │                 │ EasyOCR extract  │
  │                      │                   │                 │                 │ DeepFace compare │
  │                      │                   │                 │                 ├─write results──►│
  │                      │ poll GET /v1/jobs/{id}              │                 │ enqueue score.recompute
  │                      ├──────────────────►│◄─status─────────┤                 │                 │
  │                      │                   │                 ├────pop─────────►│ ComputeTrustScore
  │                      │                   │                 │                 ├─trust_scores ──►│
  │                      │                   │                 │◄─invalidate─────┤  + signals       │
  │◄─score + breakdown───┤◄──────────────────┤                 │  cache          │                 │
```

Key properties:
- The API returns **202 + job id** in ~50 ms; the browser never holds a 30-second connection open.
- Score recomputation is triggered by a **domain event** (`IdentityVerified`), not by the uploader —
  so *any* signal change (new phone, new listing, admin override, weight change) recomputes identically.
- Cache invalidation is the last step of the scoring job, so a stale score can never outlive a new one.

> **ASSUMPTION (A-polling):** the UI polls `GET /api/v1/jobs/{id}` every 2 s with backoff. Server-Sent
> Events are a drop-in upgrade (`GET /api/v1/jobs/{id}/stream`) if the demo needs to feel snappier;
> WebSockets are not justified for a one-way, short-lived progress feed.

## 5. Runtime flow — partner marketplace reads a score

```
Partner ──► GET /public/v1/sellers/{ref}/trust-score
              Authorization: Bearer tl_live_xxx
                 │
                 ├─ API-key middleware: prefix lookup → hash compare → scope check → status check
                 ├─ Redis token bucket per key (429 + Retry-After on exhaustion)
                 ├─ Redis GET score:{seller_id}:{model_version}       ── HIT ──► 200 (p95 < 150 ms)
                 │        │ MISS
                 │        └─ Postgres: current trust_score + signals → SETEX 300s → 200
                 └─ async: append api_request_logs (fire-and-forget, never blocks the response)
```

The public response deliberately **omits raw PII** (no CNIC number, no image URLs, no phone/email) and
returns only: score, risk level, per-signal status + contribution, reason codes, `computed_at`,
`model_version`. Buyers and partners need *why*, not *what the document said*.

## 6. Caching strategy

| Key pattern | Contents | TTL | Invalidated by |
|---|---|---|---|
| `score:{seller_id}:v{model}` | Public score payload | 300 s | Scoring job on write |
| `seller:{id}:summary` | Seller card for the web UI | 120 s | Profile/score change |
| `ratelimit:{api_key}:{window}` | Token bucket counter | window | TTL only |
| `otp:{phone_hash}` | Hashed OTP + attempt count | 300 s | Successful verify |
| `otp:throttle:{phone_hash}` | Send counter | 3600 s | TTL only |
| `idem:{key}` | Response snapshot for idempotent POSTs | 86400 s | TTL only |
| `disposable_domains` | Loaded blocklist | 86400 s | Refresh job |
| `ipintel:{ip_hash}` | IP reputation lookup result | 86400 s | TTL only |
| `arq:queue:*` | Job queue | — | ARQ |

Pattern: **cache-aside with write-through invalidation**. Never cache anything that is not also derivable
from Postgres — Redis is an accelerator, never a system of record. Losing all of Redis must cost only
latency, never data. (`ipintel` caching also protects a limited third-party quota.)

## 7. Data flow classification

| Class | Examples | Storage | Encryption | Retention |
|---|---|---|---|---|
| **Biometric / sensitive PII** | CNIC images, selfies, extracted CNIC number, DOB | Object storage (private bucket) + Postgres columns | App-level envelope encryption (AES-256-GCM) for the number/DOB; server-side encryption for objects | Images purged **90 days** after a terminal verification decision; derived hashes retained |
| **Contact PII** | Email, phone | Postgres | Hashed duplicates for lookup (`email_normalized_hash`, `phone_hash`) | Life of account + 30 days |
| **Behavioural** | Device fingerprints, IPs | Postgres (`inet`, hashed fingerprint) | — | 12 months rolling |
| **Public derived** | Trust score, risk level, reason codes | Postgres + Redis | — | Indefinite (history is the audit trail) |
| **Operational** | Logs, metrics, request logs | Log sink + Postgres | PII-redacted at the logger | 30–90 days |

This table is the reason the schema separates `identity_documents` (raw, restricted) from
`trust_score_signals` (derived, shareable): the retention job can delete the former without destroying the
score's explainability.

## 8. Failure modes and degradation

| Failure | Behaviour | Mechanism |
|---|---|---|
| LLM provider down / rate-limited | Listing analysis job retries with exponential backoff; after N attempts the `LISTING` signal is marked `UNAVAILABLE` and **excluded from the denominator** rather than scored as 0 | Signal status `UNAVAILABLE`; score normalisation over available weight |
| DeepFace/EasyOCR crash on a malformed image | Job fails cleanly → document status `FAILED` with a user-facing reason → seller re-uploads | Job-level try/except → typed `VerificationError` |
| IP-intel provider unreachable | Fall back to offline ASN/datacenter list; signal confidence lowered | `IpIntelligencePort` fallback chain |
| Redis down | API serves from Postgres; rate limiting fails **closed** for the public API, **open** for internal auth | Explicit per-limiter policy |
| Postgres down | Public API serves stale cached scores with `X-TrustLens-Stale: true`; writes return 503 | Read-path cache |
| Worker backlog | Queue depth metric alerts; API keeps accepting and returns honest queue-position estimates | ARQ queue introspection |

> **WHY "exclude, don't zero" for unavailable signals:** scoring a seller as high-risk because *our* LLM
> vendor had an outage would be unfair and unappealable. Normalising over the weight of the signals that
> actually ran keeps the score honest, and the response says which signals were unavailable.

## 9. Technology decisions worth defending

| Decision | Chosen | Alternatives rejected | Reason |
|---|---|---|---|
| Async job runner | **ARQ** | Celery, RQ, Dramatiq, FastAPI `BackgroundTasks` | ARQ is asyncio-native (matches FastAPI), uses the Redis the proposal already mandates, and is ~1/10th of Celery's configuration surface. `BackgroundTasks` is disqualified outright: work would die with the process and could not be retried or observed |
| ORM | **SQLAlchemy 2.0 (async) + Alembic** | Prisma (Python), Tortoise, raw asyncpg | Mature migrations, typed 2.0 style, escape hatch to raw SQL for the analytics views |
| Migrations | **Alembic**, one head, autogenerate + hand review | — | Autogenerated migrations are reviewed, never trusted blindly (Alembic misses enum and index changes) |
| Validation | **Pydantic v2** at the boundary, dataclasses/VOs inside the domain | Marshmallow, attrs | Pydantic is FastAPI's native validation layer and gives OpenAPI schema for free |
| Frontend rendering | **Next.js App Router**, RSC for reads + Server Actions avoided for mutations | Pure SPA (Vite), Pages Router | Public seller pages must be server-rendered and cacheable for shareability; mutations go through the typed API client so browser and server call the same contract |
| Frontend state | **TanStack Query** (server state) + Zustand (small client state) | Redux Toolkit, Context-only | Almost all state here is server state; Redux would add ceremony without benefit |
| Forms | **React Hook Form + Zod**, schemas shared from `packages/validation` | Formik | One schema validates on the client and mirrors the backend Pydantic model |
| API contract | Backend OpenAPI is the **single source of truth**; TS types + client are generated | Hand-written client, tRPC | tRPC needs a TS backend. Generation makes a breaking API change fail the frontend build — the strongest possible guardrail in a polyglot repo |
| Frontend↔backend types | `openapi-typescript` + `openapi-fetch` in `packages/api-client` | Manual duplication | Manual duplication is the #1 source of integration bugs in split-stack FYPs |

## 10. Why not microservices

The proposal describes one bounded context (seller trust) with one team of two and one release cadence.
Microservices would add network partitions, distributed transactions, and per-service CI for zero domain
benefit. The chosen shape — **modular monolith with an out-of-process worker** — keeps deployment simple
while the package boundaries (§3) make later extraction mechanical: any adapter package can become an
HTTP service by re-implementing its port over the network, with no change to `trustlens-core`.
The extraction plan is in [17 — Scalability](17-scalability.md).
