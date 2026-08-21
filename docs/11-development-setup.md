# 11 — Development Setup

## 1. Prerequisites

| Tool             | Version          | Notes                                                        |
| ---------------- | ---------------- | ------------------------------------------------------------ |
| Node.js          | 20 LTS or 22 LTS | Pinned in `.nvmrc`                                           |
| pnpm             | 9.x              | `corepack enable && corepack prepare pnpm@latest --activate` |
| Python           | 3.12             | Pinned in `.python-version`                                  |
| uv               | 0.5+             | `curl -LsSf https://astral.sh/uv/install.sh \| sh`           |
| Docker + Compose | 24+              | Runs Postgres, Redis, MinIO, MailHog                         |
| Git              | 2.40+            |                                                              |
| Make             | any              | Cross-language task entry point                              |

System libraries needed by the worker only (Docker handles this; native installs need them):
`libgl1`, `libglib2.0-0` for OpenCV.

> **The worker's ML dependency set (torch/tensorflow via DeepFace, EasyOCR) is large (~2–3 GB) and slow to
> install.** Install it once, keep it out of the API environment, and prefer the Docker worker image on
> low-spec machines.

## 2. First-time setup

```bash
git clone https://github.com/<org>/trustlens.git
cd trustlens
make setup            # everything below, in order
```

`make setup` runs:

```bash
pnpm install                                   # JS workspace
uv sync --all-packages                         # Python workspace (single lockfile)
cp .env.example .env                           # then edit secrets
docker compose up -d postgres redis minio mailhog
./scripts/check-env.py                         # fails fast on missing/invalid vars
make migrate                                   # alembic upgrade head
make seed                                      # reference data (roles, signals, scoring model v1)
make seed-demo                                 # demo sellers across all three risk bands
pnpm codegen                                   # OpenAPI → packages/api-client
pnpm --filter @trustlens/e2e exec playwright install --with-deps
pnpm husky install
```

Local service URLs:

| Service                              | URL                        | Credentials                 |
| ------------------------------------ | -------------------------- | --------------------------- |
| Web                                  | http://localhost:3000      | —                           |
| API                                  | http://localhost:8000      | —                           |
| API docs (Swagger)                   | http://localhost:8000/docs | —                           |
| Postgres                             | localhost:5432             | `trustlens` / `trustlens`   |
| Redis                                | localhost:6379             | —                           |
| MinIO console                        | http://localhost:9001      | `minioadmin` / `minioadmin` |
| MailHog (catches all outbound email) | http://localhost:8025      | —                           |

Demo accounts seeded by `make seed-demo`:

| Email                       | Password             | Role                           |
| --------------------------- | -------------------- | ------------------------------ |
| `admin@trustlens.dev`       | `Admin!Passw0rd123`  | ADMIN                          |
| `reviewer@trustlens.dev`    | `Review!Passw0rd123` | REVIEWER                       |
| `seller.high@trustlens.dev` | `Seller!Passw0rd123` | SELLER — score ≈ 85 (LOW risk) |
| `seller.mid@trustlens.dev`  | `Seller!Passw0rd123` | SELLER — score ≈ 55 (MEDIUM)   |
| `seller.low@trustlens.dev`  | `Seller!Passw0rd123` | SELLER — score ≈ 22 (HIGH)     |
| `buyer@trustlens.dev`       | `Buyer!Passw0rd123`  | BUYER                          |

Three seeded sellers spanning all three bands exist so the demo, the E2E suite, and any UI work always
have something meaningful to render without running the AI pipeline first.

## 3. Running

```bash
make dev            # web + api + worker together, prefixed colour-coded logs
make dev-web        # Next.js only               → :3000
make dev-api        # FastAPI --reload only      → :8000
make dev-worker     # ARQ worker only
make dev-offline    # everything with USE_FAKE_AI=true — no external API keys needed
```

`make dev-offline` is what makes the FYP demonstrable on a lab machine with no internet or no paid keys
(NFR-8): every external port resolves to its fake — `FakeOcrEngine` returns fixture text, `StubLlmAnalyzer`
returns a canned analysis, the console sender prints OTPs and emails to stdout.

## 4. Build

```bash
make build          # turbo run build (JS) + python -m build (packages)
pnpm build          # JS only
pnpm --filter web build
docker compose -f docker/compose/docker-compose.full.yml build
```

## 5. Database

```bash
make migrate                        # alembic upgrade head
make migrate-down                   # alembic downgrade -1
make migration m="add scoring weights"   # autogenerate — ALWAYS hand-review the output
make db-reset                       # drop → create → migrate → seed  (destructive, confirms first)
make db-shell                       # psql into the dev database
make db-backup / make db-restore f=backups/2026-07-30.dump
make seed                           # idempotent reference data
make seed-demo                      # demo data (dev only; refuses to run when ENV=production)
```

Alembic autogenerate reliably misses **enum value additions, partial-index predicates, check constraints,
and column type changes on Postgres enums**. Every generated migration is read line by line before commit.

## 6. Testing

```bash
make test                 # everything
make test-py              # pytest across all Python packages/apps
make test-js              # vitest across all JS packages/apps
make test-unit            # fast: domain + policies + components, no I/O
make test-integration     # testcontainers: real Postgres + Redis
make test-e2e             # Playwright (starts the full stack)
make test-e2e-ui          # Playwright in headed/debug mode
make test-contract        # Schemathesis fuzzes the live OpenAPI doc
make test-load            # k6 against the public score endpoint
make coverage             # combined report; CI gate at 80% overall, 95% on trustlens-core
```

Details in [14 — Testing Strategy](14-testing-strategy.md).

## 7. Code quality

```bash
make lint                 # ruff + eslint + markdownlint
make lint-fix
make format               # black + ruff format + prettier
make typecheck            # mypy --strict (Python) + tsc --noEmit (TS)
make check-arch           # import-linter: enforces the dependency rules in 02 §3
make check-deps           # unused/undeclared dependency detection (knip, deptry)
make audit                # pnpm audit + pip-audit + gitleaks
make ci                   # exactly what CI runs — run before pushing
```

## 8. Codegen

```bash
pnpm codegen              # OpenAPI → packages/api-client (types + typed client)
make openapi              # export apps/api OpenAPI → docs/api/openapi.json
make erd                  # database/erd/schema.dbml → erd.svg
make postman              # OpenAPI → Postman collection
pnpm gen:feature <name>   # scaffold a frontend feature slice
pnpm gen:usecase <name>   # scaffold a backend use case + test
```

`pnpm codegen` must be run after **any** API schema change. CI regenerates and fails if the committed
output differs — a backend field rename then breaks the frontend type-check in the same PR, which is
exactly where it should break.

## 9. Deployment commands

```bash
make deploy-staging       # push to develop → CI deploys automatically
make deploy-prod          # tag a release → CI deploys after approval
railway run --service api alembic upgrade head    # migrations run as a release step, not at boot
vercel --prod             # manual frontend deploy (normally automatic on main)
```

Migrations are a **release step**, never an app-startup step: two API replicas booting simultaneously
would otherwise race to run the same migration. See [16 — Deployment](16-deployment.md).

## 10. Troubleshooting

| Symptom                                 | Cause                                                   | Fix                                                         |
| --------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------------- |
| `ImportError: libGL.so.1`               | OpenCV needs system GL libs                             | `apt install libgl1 libglib2.0-0`, or use the Docker worker |
| DeepFace downloads weights on first run | Model weights are fetched lazily                        | Pre-warm in the Dockerfile; cache `~/.deepface` in a volume |
| `port 5432 already in use`              | A local Postgres is running                             | Stop it, or set `POSTGRES_PORT=5433` in `.env`              |
| Frontend types out of date              | OpenAPI changed                                         | `pnpm codegen`                                              |
| Jobs enqueue but never run              | Worker not running / wrong Redis DB                     | `make dev-worker`; confirm `REDIS_URL` matches in both apps |
| OTP/email never arrives                 | Console/MailHog sender in dev                           | Check worker stdout or http://localhost:8025                |
| `alembic` sees no changes               | Model not imported in `trustlens-db/models/__init__.py` | Add the import                                              |
| Turbo serves a stale build              | Cache                                                   | `pnpm turbo run build --force`                              |
| Playwright fails on first run           | Browsers not installed                                  | `pnpm exec playwright install --with-deps`                  |
