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
