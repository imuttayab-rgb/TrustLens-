# 10 — Folder Structure Guide

## 1. Root

```
trustlens/
├── apps/                 # Deployable units. Thin — they wire packages together.
├── packages/             # Shared libraries. TS in packages/*, Python in packages/py/*.
├── database/             # Migrations, seeds, ERD, hand-written SQL. One home for schema truth.
├── infrastructure/       # Dockerfiles, compose, platform config, observability.
├── configs/              # Cross-cutting tool configuration shared by apps and packages.
├── docs/                 # This documentation set.
├── scripts/              # Developer and CI scripts.
├── testing/              # Cross-app tests that belong to no single app.
├── tools/                # Repo-local generators (OpenAPI → TS client, ERD renderer).
├── .github/              # CI/CD workflows, templates, CODEOWNERS.
├── .husky/               # Git hooks.
├── .vscode/              # Shared editor settings + recommended extensions.
├── package.json          # pnpm workspace root; JS scripts delegate to turbo.
├── pnpm-workspace.yaml
├── turbo.json            # Task graph + cache inputs/outputs.
├── pyproject.toml        # uv workspace root; shared Ruff/Black/mypy/pytest config.
├── uv.lock
├── Makefile              # ONE entry point across both languages: make dev / test / migrate.
├── docker-compose.yml    # Local Postgres, Redis, MinIO, MailHog.
├── .env.example
├── .editorconfig  .gitignore  .gitattributes  .nvmrc  .python-version
├── ARCHITECTURE.md  README.md  CONTRIBUTING.md  LICENSE  CHANGELOG.md
```

### Why some commonly-suggested top-level folders are *not* here

| Suggested | Decision | Reason |
|---|---|---|
| `backend/`, `frontend/` | **Merged into `apps/`** | Two competing conventions for "a deployable thing" is worse than one. `apps/api` + `apps/web` is unambiguous and is what Turborepo/Vercel expect |
| `shared/` | **Merged into `packages/`** | Two shared locations guarantees drift — nobody can answer "does this go in `shared/` or `packages/`?" consistently |
| `src/` at the root | Not used | Meaningless in a monorepo; each app/package has its own `src/` |
| `services/` | Not used | `apps/worker` *is* the only extra service today; a `services/` folder would imply a microservice split that does not exist ([02 §10](02-system-architecture.md)) |
| `libs/` | Not used | Nx vocabulary; `packages/` is the pnpm/Turborepo convention |

## 2. `apps/`

```
apps/
├── web/          # Next.js — every human UI (public, seller, admin). → Vercel
├── api/          # FastAPI — internal + public REST API. → Railway
├── worker/       # ARQ — OCR, face match, LLM, scoring, webhooks, cron. → Railway
└── ml/           # Offline: trains/evaluates/versions the scam-listing classifier.
```

| App | Detailed structure |
|---|---|
| `web` | [04 — Frontend Architecture §2](04-frontend-architecture.md) |
| `api` | [03 — Backend Architecture §3](03-backend-architecture.md) |
| `worker` | [03 §4](03-backend-architecture.md) |
| `ml` | below |

### `apps/ml`

```
apps/ml/
├── pyproject.toml
├── README.md                # how to retrain and publish a model
├── data/
│   ├── raw/                 # gitignored — source listing datasets
│   ├── processed/           # gitignored — cleaned/split
│   └── labels/              # ★ committed: the hand-labelled ground truth (small, precious)
├── notebooks/               # exploration only; nothing importable lives here
├── src/trustlens_ml/
│   ├── config.py
│   ├── datasets/            # loading, cleaning, stratified splits
│   ├── features/            # imports trustlens.ai.classifier.features — NO reimplementation
│   ├── training/            # train.py, hyperparameter search, cross-validation
│   ├── evaluation/          # metrics, confusion matrix, per-slice fairness report
│   └── registry/            # versions + uploads artifacts to object storage
├── models/                  # gitignored artifacts; the registry is the source of truth
└── reports/                 # committed evaluation reports per model version
```

> **WHY `features/` imports rather than reimplements:** training/serving feature skew is the classic way
> a classifier scores 0.94 offline and behaves randomly in production. One implementation, two callers.
> `data/labels/` is committed because the labelled dataset is the most expensive artifact the team will
> produce and must be reviewable and reproducible.

## 3. `packages/`

```
packages/
├── ui/                 # Design system: Radix + CVA + Tailwind. Shipped as source.
├── api-client/         # GENERATED typed client + types from the backend OpenAPI doc. Do not hand-edit.
├── validation/         # Zod schemas shared by forms and the BFF.
├── constants/          # Cross-app constants: risk bands, signal codes, reason codes, routes.
├── utils/              # Framework-free TS helpers (format, dates, guards).
├── i18n/               # Message catalogues + typed t(). English only for now (A12).
├── config-eslint/      # Flat ESLint configs: base, react, next, node.
├── config-typescript/  # tsconfig bases: base, react-library, nextjs.
├── config-tailwind/    # Shared Tailwind preset + design tokens.
└── py/
    ├── trustlens-core/     # Domain + use cases + PORTS. Zero framework imports.
    ├── trustlens-db/       # SQLAlchemy models, repositories, unit of work.
    ├── trustlens-ai/       # OCR, face match, LLM, classifier adapters.
    ├── trustlens-shared/   # Config, logging, storage, cache, queue, crypto, notifications, IP intel.
    └── trustlens-testing/  # Shared pytest fixtures, factories, in-memory fakes, contract tests.
```

Package rules:
- Each package has its own `package.json` / `pyproject.toml`, `README.md`, and tests.
- Every package exports through a single public entry point (`src/index.ts` or `__init__.py`); deep
  imports into another package's internals are lint errors.
- A package may not depend on an app. `trustlens-core` may not depend on any other package.
- `api-client/src/*.gen.ts` is generated; CI regenerates and fails on drift.

`packages/constants` is small but load-bearing: risk-band thresholds, signal codes, and reason codes
appear in the backend, the frontend, and the docs. One TypeScript module plus one Python module
(`trustlens-core/domain/enums`) generated from the same source of truth keeps them from diverging into a
bug nobody notices until a demo.

### `packages/py/trustlens-testing`

Exists so that `apps/api`, `apps/worker`, and every package share **one** set of fakes:
`InMemoryUserRepository`, `FakeOcrEngine`, `FakeFaceMatcher`, `StubLlmAnalyzer`, `FrozenClock`,
`FakeStorage`, plus `factory-boy` factories for every entity and the **port contract test suites** that
every real adapter must pass. Without it, each app grows its own subtly-different mocks and tests stop
proving anything about production behaviour.

## 4. `database/`

```
database/
├── alembic.ini
├── migrations/
│   ├── env.py                 # imports metadata from packages/py/trustlens-db
│   ├── script.py.mako
│   └── versions/              # YYYYMMDDHHMM_<slug>.py — one head, always
├── seeds/
│   ├── reference/             # idempotent: roles, permissions, signal_definitions, scoring model v1
│   └── demo/                  # dev/E2E only: sellers across all three risk bands
├── sql/
│   ├── functions/             # PL/pgSQL helpers (partition maintenance)
│   ├── views/                 # analytics/read-model views for the admin dashboard
│   └── partitions/            # monthly partition creation for the append-only tables
└── erd/
    ├── schema.dbml            # source of truth for the diagram
    └── erd.svg                # generated by tools/erd
```

> **WHY migrations live here rather than inside `packages/py/trustlens-db`:** both `api` and `worker`
> depend on the models package, but only **one** process should ever run migrations, and CI/CD needs a
> single unambiguous path (`database/`) for the migrate step. `env.py` imports the metadata from the
> package, so models and migrations still have a single source of truth.

## 5. `infrastructure/`

```
infrastructure/
├── docker/
│   ├── api.Dockerfile          # slim, no ML deps, multi-stage, non-root
│   ├── worker.Dockerfile       # ML deps, pinned system libs for OpenCV
│   ├── web.Dockerfile          # only for self-hosting; Vercel builds natively
│   └── base.Dockerfile
├── compose/
│   ├── docker-compose.dev.yml  # Postgres, Redis, MinIO, MailHog
│   ├── docker-compose.test.yml # ephemeral, tmpfs volumes, no ports published
│   └── docker-compose.full.yml # everything containerised, for a clean-machine demo
├── railway/
│   ├── railway.json            # service definitions, health checks
│   └── README.md               # env var provisioning per service
├── vercel/
│   └── vercel.json             # headers, redirects, region
├── observability/
│   ├── otel-collector.yaml
│   ├── prometheus.yml
│   └── dashboards/             # committed JSON dashboards
└── scripts/
    ├── wait-for-it.sh
    └── entrypoint.sh
```

## 6. `configs/`

```
configs/
├── commitlint.config.js     # Conventional Commits
├── lint-staged.config.js    # JS → prettier+eslint; PY → ruff+black
├── prettier.config.js
├── renovate.json            # grouped, scheduled dependency updates
├── .markdownlint.json
├── .yamllint.yml
└── codecov.yml
```

Kept out of the root so the root listing stays readable, and so config is versioned as a single reviewable
unit. Tools that hard-require root files (e.g. `.editorconfig`) stay at the root and are the exception.

## 7. `scripts/`

```
scripts/
├── setup.sh              # one-command bootstrap: deps, .env, docker up, migrate, seed
├── dev.sh                # run web + api + worker concurrently with prefixed logs
├── db-reset.sh           # drop → migrate → seed (destructive; requires confirmation)
├── db-backup.sh / db-restore.sh
├── generate-api-client.sh# export OpenAPI → codegen → format
├── export-postman.sh     # OpenAPI → Postman collection (a proposal-listed tool)
├── check-env.py          # validates .env against .env.example; fails on missing keys
├── seed-demo.py          # demo sellers for the presentation
└── ci/                   # scripts invoked by GitHub Actions
```

Rule: anything a developer would otherwise paste from a README belongs here. A README command that drifts
from reality is a bug that only surfaces on someone else's machine.

## 8. `testing/`

```
testing/
├── e2e/                  # Playwright: full user journeys across web + api + worker
│   ├── specs/            # auth, seller-verification, trust-score, appeals, admin, public-api
│   ├── fixtures/         # seeded users, sample CNIC/selfie images (synthetic only)
│   ├── page-objects/
│   └── playwright.config.ts
├── contract/             # Schemathesis fuzzing against the live OpenAPI doc
├── load/                 # k6: public score endpoint, login, upload intent
├── security/             # ZAP baseline config, dependency/secret scan configs
└── data/                 # shared synthetic test data — NEVER real CNIC images
```

> `testing/data` carries an explicit rule: only **synthetic** identity documents. Real CNIC scans in a
> git repository would be an irreversible data-protection failure. A generator script produces
> realistic-but-fake CNIC images for OCR tests.

## 9. `tools/`

```
tools/
├── codegen/         # OpenAPI → packages/api-client (openapi-typescript + openapi-fetch)
├── erd/             # database/erd/schema.dbml → erd.svg
├── openapi/         # bundling, linting (spectral), diffing for breaking-change detection
└── generators/      # plop templates: new feature slice, new use case, new adapter
```

`tools/generators` is disproportionately valuable on a 2-person team: `pnpm gen:feature listings`
scaffolds the folder, index, hooks, and test files in the agreed shape, so structure conventions are
enforced by a generator instead of by review comments.

## 10. Naming conventions

| Thing | Convention | Example |
|---|---|---|
| Directories | `kebab-case` | `verification-identity/` |
| React components | `PascalCase.tsx` | `ScoreGauge.tsx` |
| React hooks | `useThing.ts` | `useTrustScore.ts` |
| Other TS modules | `kebab-case.ts` | `query-keys.ts` |
| TS types/interfaces | `PascalCase`, no `I` prefix | `TrustScoreSummary` |
| TS constants | `SCREAMING_SNAKE_CASE` | `MAX_UPLOAD_BYTES` |
| Feature-scoped TS files | `<name>.<kind>.ts` | `auth.api.ts`, `listing.schema.ts` |
| Test files (TS) | `*.test.ts(x)` beside the source; E2E `*.spec.ts` | `ScoreGauge.test.tsx` |
| Python modules/packages | `snake_case` | `trust_score.py` |
| Python classes | `PascalCase` | `ComputeTrustScore` |
| Python functions/vars | `snake_case` | `compute_trust_score` |
| Python constants | `SCREAMING_SNAKE_CASE` | `DEFAULT_SCORE_TTL` |
| Python protocols (ports) | Noun, no `I`/`Abstract` prefix | `OcrEngine`, `TrustScoreRepository` |
| Test files (Python) | `test_*.py` mirroring the source tree | `test_scoring_policy.py` |
| DB tables/columns | `snake_case`, plural tables | `trust_score_signals` |
| Alembic revisions | `YYYYMMDDHHMM_<slug>.py` | `202607301200_add_scoring_weights.py` |
| Env vars | `SCREAMING_SNAKE_CASE`, prefixed by domain | `AI_OPENAI_API_KEY` |
| API routes | `kebab-case`, plural nouns | `/api/v1/trust-scores` |
| JSON fields | `camelCase` | `riskLevel` |
| Git branches | `<type>/<issue>-<slug>` | `feat/42-cnic-ocr-pipeline` |

## 11. Where does new code go? (decision guide)

| I am adding… | It goes in |
|---|---|
| A business rule | `packages/py/trustlens-core/domain/policies/` |
| A new user-triggered operation | `packages/py/trustlens-core/application/use_cases/<area>/` |
| A new HTTP endpoint | `apps/api/src/trustlens_api/api/v1/routers/` + a schema in `.../schemas/` |
| A new third-party integration | A **port** in `trustlens-core/domain/ports/` + an adapter in `trustlens-shared` or `trustlens-ai` |
| A new database table | Model in `trustlens-db/models/`, migration in `database/migrations/`, repository in `trustlens-db/repositories/` |
| A new background job | `apps/worker/src/trustlens_worker/jobs/` (thin — it calls a use case) |
| A new page | `apps/web/src/app/<group>/…/page.tsx` (routing only) |
| Page logic/components | `apps/web/src/features/<feature>/` |
| A reusable, feature-agnostic UI primitive | `packages/ui/src/primitives/` |
| A shared Zod schema | `packages/validation/src/` |
| A new scoreable signal | `signal_definitions` seed row + a collector in `trustlens-core/application/services/` + a weight in `scoring_weights` — **the scoring policy is not modified** |
