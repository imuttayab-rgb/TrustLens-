.DEFAULT_GOAL := help
SHELL := /bin/bash
COMPOSE := docker compose -f docker/compose/docker-compose.dev.yml
UV := uv run
export PYTHONPATH := $(CURDIR)

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────
.PHONY: setup
setup: ## One-command bootstrap: deps, env, services, migrations, seed
	@echo "==> Installing JS dependencies"; pnpm install
	@echo "==> Installing Python dependencies"; uv sync --all-packages --dev
	@[ -f .env ] || (cp .env.example .env && echo "==> Created .env from .env.example")
	@echo "==> Starting infrastructure"; $(COMPOSE) up -d
	@bash scripts/wait-for-services.sh
	@$(MAKE) migrate seed
	@echo ""
	@echo "Setup complete.  Run 'make dev' to start."

.PHONY: install
install: ## Install dependencies only
	pnpm install && uv sync --all-packages --dev

# ── Infrastructure ───────────────────────────────────────────────────
.PHONY: up down logs ps
up: ## Start Postgres, Redis, MinIO, MailHog
	$(COMPOSE) up -d && bash scripts/wait-for-services.sh
down: ## Stop infrastructure (keeps volumes)
	$(COMPOSE) down
nuke: ## Stop infrastructure AND delete all volumes
	$(COMPOSE) down -v
logs: ## Tail infrastructure logs
	$(COMPOSE) logs -f
ps: ## Show infrastructure status
	$(COMPOSE) ps

# ── Development ──────────────────────────────────────────────────────
.PHONY: dev dev-web dev-admin dev-api dev-worker dev-offline
dev: ## Run api + worker + web + admin together
	bash scripts/dev.sh
dev-web: ## Next.js public/seller app on :3000
	pnpm --filter @trustlens/web dev
dev-admin: ## Next.js admin app on :3001
	pnpm --filter @trustlens/admin dev
dev-api: ## FastAPI on :8000
	$(UV) uvicorn trustlens_api.main:app --reload --host 0.0.0.0 --port 8000
dev-worker: ## ARQ worker
	$(UV) python -m trustlens_worker.supervisor
dev-offline: ## Everything with USE_FAKE_AI=true (no keys, no internet)
	USE_FAKE_AI=true bash scripts/dev.sh

# ── Database ─────────────────────────────────────────────────────────
.PHONY: migrate migrate-down migration seed seed-demo db-reset db-shell db-backup
migrate: ## Apply all migrations
	cd database && $(UV) alembic upgrade head
migrate-down: ## Roll back one migration
	cd database && $(UV) alembic downgrade -1
migration: ## Autogenerate a migration: make migration m="add x"
	cd database && $(UV) alembic revision --autogenerate -m "$(m)"
	@echo "!! Review the generated migration by hand - autogenerate misses enums, partial indexes and checks."
seed: ## Seed reference data (roles, permissions, signals, scoring model v1)
	$(UV) python -m trustlens.db.seed.run reference
seed-demo: ## Seed demo sellers across all three risk bands (dev only)
	$(UV) python -m trustlens.db.seed.run demo
db-reset: ## Drop, recreate, migrate and seed (DESTRUCTIVE)
	bash scripts/db-reset.sh
db-shell: ## psql into the dev database
	$(COMPOSE) exec postgres psql -U trustlens -d trustlens
db-backup: ## Dump the dev database to backups/
	bash scripts/db-backup.sh

# ── Quality ──────────────────────────────────────────────────────────
.PHONY: lint format typecheck check-arch
lint: ## Lint everything
	$(UV) ruff check .
	pnpm lint
format: ## Format everything
	$(UV) ruff format . && $(UV) ruff check --fix .
	pnpm format
typecheck: ## Static type checks (mypy + tsc)
	$(UV) mypy packages/py apps/api/src apps/worker/src
	pnpm typecheck
check-arch: ## Enforce the layering contracts (ADR-0003, ADR-0004)
	$(UV) lint-imports --config .importlinter

# ── Tests ────────────────────────────────────────────────────────────
.PHONY: test test-py test-js test-unit test-integration test-e2e test-contract coverage
test: test-py test-js ## Run the full test suite
test-py: ## Python tests
	$(UV) pytest
test-js: ## JS/TS tests
	pnpm test
test-unit: ## Fast unit tests only (no I/O)
	$(UV) pytest -m "not integration and not slow"
test-integration: ## Integration tests (testcontainers: real Postgres + Redis)
	$(UV) pytest -m integration
test-e2e: ## Playwright end-to-end tests
	pnpm --filter @trustlens/e2e test
test-contract: ## Schemathesis fuzzing against the live OpenAPI document
	$(UV) schemathesis run http://localhost:8000/openapi.json --checks all
coverage: ## Coverage report
	$(UV) pytest --cov --cov-report=term-missing --cov-report=html

# ── Codegen ──────────────────────────────────────────────────────────
.PHONY: openapi codegen erd postman
openapi: ## Export the OpenAPI document
	$(UV) python -m trustlens_api.openapi_export > docs/api/openapi.json
codegen: openapi ## Regenerate the typed API client from OpenAPI
	pnpm codegen
erd: ## Render the ER diagram
	bash tools/erd/generate.sh
postman: openapi ## Generate the Postman collection
	bash scripts/export-postman.sh

# ── Build & CI ───────────────────────────────────────────────────────
.PHONY: build ci clean
build: ## Build all apps and packages
	pnpm build
ci: lint typecheck check-arch test ## Exactly what CI runs
clean: ## Remove build artifacts and caches
	rm -rf .turbo node_modules/.cache **/.next **/dist **/.pytest_cache **/.mypy_cache **/.ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

# ── Production, locally ──────────────────────────────────────────────
#
# The whole product in production mode on one machine: built Next.js servers,
# uvicorn with workers, migrations as a release step, health checks, restart
# policies. This is the handover artifact - the students can run it on a
# laptop, or point it at hosted Postgres/Redis/S3 later by editing URLs in
# .env.production. Nothing here assumes a particular platform.
.PHONY: prod-init prod-build prod-up prod-down prod-logs prod-ps prod-restart prod-nuke prod-check prod-security prod-backup prod-backup-verify

PROD_COMPOSE := docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production

prod-init: ## Create .env.production with freshly generated secrets
	@test ! -f .env.production || (echo "!! .env.production already exists - refusing to overwrite secrets" && exit 1)
	cp .env.production.example .env.production
	bash scripts/generate-keys.sh >> .env.production
	@echo ""
	@echo "==> .env.production created with real secrets."
	@echo "==> NOW EDIT IT: change POSTGRES_PASSWORD and STORAGE_SECRET_ACCESS_KEY,"
	@echo "    and make DATABASE_URL / DATABASE_URL_SYNC use the same password."
	@echo "==> Then: make prod-up"

prod-build: ## Build all four images (do this after changing any NEXT_PUBLIC_* value)
	$(PROD_COMPOSE) build

prod-up: ## Start the full production stack in the background
	$(PROD_COMPOSE) up -d --build
	@echo ""
	@echo "  web    http://localhost:3000"
	@echo "  admin  http://localhost:3001"
	@echo "  api    http://localhost:8000/docs"
	@echo "  mail   http://localhost:8025"
	@echo ""
	@echo "  make prod-check   verify every service is actually healthy"

prod-down: ## Stop the stack (keeps data)
	$(PROD_COMPOSE) down

prod-nuke: ## Stop the stack AND delete all data. Irreversible.
	$(PROD_COMPOSE) down -v

prod-logs: ## Tail logs from every service
	$(PROD_COMPOSE) logs -f --tail=100

prod-ps: ## Show service status and health
	$(PROD_COMPOSE) ps

prod-restart: ## Restart the app services without touching the databases
	$(PROD_COMPOSE) restart api worker web admin

prod-check: ## Verify the running stack end to end
	bash scripts/prod-check.sh

prod-security: ## Run the automated security checks against the running stack
	bash scripts/security-check.sh

prod-backup: ## Take a database backup
	bash scripts/db-backup.sh --stack prod

prod-backup-verify: ## Take a backup AND prove it restores
	bash scripts/db-backup.sh --stack prod
	bash scripts/db-restore.sh --verify --stack prod

# ── Hosted split: frontends on Vercel, database on Neon ──────────────
.PHONY: hosted-init hosted-up hosted-down hosted-logs hosted-migrate

HOSTED_COMPOSE := docker compose -f docker/compose/docker-compose.hosted.yml --env-file .env.hosted

hosted-init: ## Create .env.hosted from the template plus fresh secrets
	@test ! -f .env.hosted || (echo "!! .env.hosted exists - refusing to overwrite secrets" && exit 1)
	cp .env.hosted.example .env.hosted
	bash scripts/generate-keys.sh >> .env.hosted
	@echo ""
	@echo "==> .env.hosted created. Now fill in: Neon URLs, the public API URL,"
	@echo "    the Vercel URLs, and your Resend key. See ACCOUNTS.md."

hosted-up: ## Start api + worker (+ redis) against Neon
	$(HOSTED_COMPOSE) up -d --build

hosted-down: ## Stop the self-hosted half
	$(HOSTED_COMPOSE) down

hosted-logs: ## Tail api and worker logs
	$(HOSTED_COMPOSE) logs -f --tail=100

hosted-migrate: ## Run migrations against Neon without starting anything else
	$(HOSTED_COMPOSE) run --rm migrate
