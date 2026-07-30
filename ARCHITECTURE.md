# TrustLens — Architecture Overview

> **TrustLens – AI-Powered Seller Trust Verification System for Online Marketplaces**
> School of Software Engineering, Minhaj University Lahore — FYP (7th/8th Semester)
> Haseeb Ur Rehman (2022F-mulbsswe-043), Muhammad Muttayab (2022F-mulbsswe-012)

This document is the entry point to the TrustLens architecture. Detailed designs live in [`docs/`](docs/README.md).

---

## 1. What the system does

TrustLens verifies whether an online marketplace seller is **genuine or fake** and publishes a single
**explainable Trust Score (0–100)** with a risk level and the reasons behind it.

It does this by collecting **seven independent signal families**, each of which a scammer would have to
defeat separately:

| # | Signal family | Evidence gathered | Proposal feature |
|---|---------------|-------------------|------------------|
| 1 | **Identity** | CNIC OCR (EasyOCR + OpenCV) + selfie↔CNIC face match (DeepFace) | "identity verification (CNIC OCR + face match)" |
| 2 | **Phone** | OTP challenge, VOIP/disposable-number detection | "phone OTP" |
| 3 | **Email** | Verification link, disposable-domain and domain-age checks | "email checks" |
| 4 | **Device** | Device fingerprint, multi-account-per-device clustering | "device … detection" |
| 5 | **Network** | IP reputation, VPN / proxy / datacenter detection, geo consistency | "IP / VPN detection" |
| 6 | **Behaviour** | Account age, activity history, verification recency | "account age" (problem statement) |
| 7 | **Listing content** | LLM (OpenAI / Claude) + custom-trained scam-listing classifier | "AI listing analysis" |

Those signals feed a **versioned, deterministic scoring engine** that emits the score, the risk band, and a
per-signal breakdown. Sellers who disagree can **appeal**; admins review through an **admin panel**.
Partner marketplaces read scores through a **public REST API** secured by API keys.

---

## 2. The three architectural decisions that shape everything else

### D1 — The score is computed by deterministic rules; AI is an *input*, never the judge

An LLM is non-deterministic and cannot be audited or appealed. So the AI models (Claude/OpenAI, DeepFace,
EasyOCR, the scam classifier) produce **evidence with a confidence value**; a versioned rule set
(`scoring_models` + `signal_definitions` in the database) converts evidence into points.

Consequences:
- The same seller state + the same model version always yields the same score → **reproducible, appealable**.
- Every score persists its **full signal breakdown snapshot** (`trust_score_signals`) → the "explainable"
  requirement is satisfied by construction, not by asking an LLM to explain itself.
- Weights are tunable by admins **without a redeploy**, and old scores stay valid because they reference
  the model version that produced them.
- The LLM may still *write* the human-readable reason text — but only by rephrasing facts the rule engine
  already decided.

See [`docs/08-trust-score-engine.md`](docs/08-trust-score-engine.md).

### D2 — The API is thin and synchronous; all AI work is asynchronous

EasyOCR, OpenCV, and DeepFace pull in heavy native/ML dependencies (torch, tensorflow, opencv) and take
seconds to tens of seconds. Putting them in the request path would blow the API's memory footprint, cold
start, and p99 latency — and Railway containers are small.

So: `apps/api` (FastAPI, thin, ~200 MB image) accepts uploads and **enqueues jobs**; `apps/worker`
(ARQ over the Redis that the proposal already requires) runs the AI. The frontend polls or subscribes to
job status. Score *reads* stay sub-100 ms because they hit a Redis-cached, precomputed row.

This directly delivers the proposal's "**return an explainable seller Trust Score within seconds**": the
*read* is instant; the *computation* happens once, in the background, when evidence changes.

### D3 — Domain logic lives in framework-free Python packages, not in FastAPI

`packages/py/trustlens-core` contains entities, value objects, use cases, and **ports** (Protocols) with
zero imports of FastAPI, SQLAlchemy, or any vendor SDK. Adapters implement the ports:

```
trustlens-core  (domain + use cases + ports)      ← depends on nothing
        ▲            ▲              ▲
        │            │              │
   trustlens-db  trustlens-ai  trustlens-shared    ← adapters (SQLAlchemy, OpenAI/Claude, Redis, S3)
        ▲            ▲              ▲
        └──────┬─────┴──────────────┘
          apps/api   apps/worker                   ← composition roots (wire adapters into ports)
```

Consequences: the same use case (`ComputeTrustScore`) is called identically from an HTTP route, a
background job, and a test — with an in-memory repository in the test. Swapping OpenAI for Claude, or
EasyOCR for a cloud OCR, is a one-file adapter change. This is Dependency Inversion (the "D" in SOLID)
applied at the package boundary so the compiler/linter can enforce it.

---

## 3. System context

```
┌──────────────┐        ┌───────────────────┐        ┌──────────────────┐
│   Buyer      │        │  Seller           │        │  Admin /         │
│  (public     │        │  (verification    │        │  Reviewer        │
│   lookup)    │        │   + appeals)      │        │  (panel)         │
└──────┬───────┘        └─────────┬─────────┘        └────────┬─────────┘
       │                          │                           │
       └──────────────┬───────────┴───────────────────────────┘
                      ▼
          ┌───────────────────────────┐
          │  apps/web  — Next.js      │   Vercel
          │  (App Router, Tailwind)   │
          └───────────┬───────────────┘
                      │ HTTPS (JWT cookie/bearer)
                      ▼
┌──────────────────────────────────────────────────┐
│  apps/api — FastAPI                              │   Railway
│  /api/v1/**    internal (JWT + RBAC)             │
│  /public/v1/** partner API (API key + quota)     │◄────── Partner marketplace
└───┬───────────────┬──────────────┬───────────────┘        (OLX-style, rentals,
    │               │              │                          vehicles, freelance)
    │ SQL           │ enqueue/cache│ signed URLs
    ▼               ▼              ▼
┌─────────┐   ┌───────────┐   ┌──────────────┐
│Postgres │   │  Redis    │   │Object storage│
│         │   │ queue +   │   │(CNIC, selfie,│
│         │   │ cache +   │   │ listing imgs)│
│         │   │ ratelimit │   └──────────────┘
└────▲────┘   └─────▲─────┘
     │              │ jobs
     │        ┌─────┴──────────────────────────┐
     └────────┤ apps/worker — ARQ              │   Railway
              │ OCR · face match · listing AI  │
              │ · scoring · webhooks · cleanup │
              └────┬──────────┬────────────────┘
                   │          │
                   ▼          ▼
            ┌────────────┐  ┌──────────────────────┐
            │ OpenCV     │  │ OpenAI / Claude API  │
            │ EasyOCR    │  │ IP-intel provider    │
            │ DeepFace   │  │ SMS (OTP) · Email    │
            │ Classifier │  └──────────────────────┘
            └────────────┘
```

---

## 4. Repository layout (top level)

```
trustlens/
├── apps/            # Deployable units: web, api, worker, ml
├── packages/        # Shared libraries: TypeScript in packages/*, Python in packages/py/*
├── database/        # Alembic migrations, seeds, ERD, hand-written SQL
├── infrastructure/  # Dockerfiles, compose, Railway/Vercel config, observability
├── configs/         # Cross-cutting tool config (commitlint, lint-staged, renovate…)
├── docs/            # This architecture documentation
├── scripts/         # Developer/CI shell + Python scripts
├── testing/         # Cross-app tests: E2E (Playwright), load (k6), contract (Schemathesis)
├── tools/           # Repo-local generators & codegen (OpenAPI → TS client)
└── .github/         # CI/CD workflows, PR/issue templates, CODEOWNERS
```

Full tree with the purpose of every folder: [`docs/10-folder-structure.md`](docs/10-folder-structure.md).

---

## 5. Documentation map

| Doc | Covers |
|-----|--------|
| [01 Project Overview](docs/01-project-overview.md) | Requirements traced from the proposal, scope, personas, assumptions |
| [02 System Architecture](docs/02-system-architecture.md) | C4 views, runtime flows, monorepo tooling, technology decisions |
| [03 Backend Architecture](docs/03-backend-architecture.md) | Clean-architecture layers, modules, DI, middleware, errors, logging |
| [04 Frontend Architecture](docs/04-frontend-architecture.md) | Next.js App Router, feature-slice layout, state, forms, API layer |
| [05 Database Design](docs/05-database-design.md) | ERD, 30 tables, enums, constraints, indexes, audit & soft delete |
| [06 API Design](docs/06-api-design.md) | Versioning, endpoints, envelopes, RFC 9457 errors, pagination |
| [07 Auth & Authorization](docs/07-authentication-authorization.md) | JWT + refresh rotation, RBAC, API keys, protected routes |
| [08 Trust Score Engine](docs/08-trust-score-engine.md) | Signals, weights, caps, explainability, recomputation triggers |
| [09 User Roles](docs/09-user-roles.md) | Roles, permission matrix, journeys per persona |
| [10 Folder Structure](docs/10-folder-structure.md) | Every directory and why it exists |
| [11 Development Setup](docs/11-development-setup.md) | Install, run, build, migrate, seed, test commands |
| [12 Environment Variables](docs/12-environment-variables.md) | Every variable, per environment, with explanations |
| [13 Coding Standards](docs/13-coding-standards.md) | Naming, Git workflow, commits, ESLint/Prettier/Ruff, Husky |
| [14 Testing Strategy](docs/14-testing-strategy.md) | Unit, integration, contract, E2E, load, AI evaluation |
| [15 Security](docs/15-security.md) | Threat model, PII/biometric handling, OWASP controls |
| [16 Deployment](docs/16-deployment.md) | Vercel + Railway pipelines, environments, migrations, rollback |
| [17 Scalability](docs/17-scalability.md) | Caching, queues, extraction to services, observability |
| [18 Contribution Guide](docs/18-contributing.md) | Branching, PR checklist, review rules for a 2-person team |
| [19 Future Improvements](docs/19-future-improvements.md) | The proposal's future scope, sequenced |
| [ADRs](docs/adr/) | Point-in-time decision records with alternatives considered |

---

## 6. Status

This is a **design deliverable**. No implementation code has been written yet; the folder trees below are
specifications for the scaffold, not generated files. Recommended build order is in
[`docs/01-project-overview.md`](docs/01-project-overview.md#8-recommended-build-order-8th-semester).
