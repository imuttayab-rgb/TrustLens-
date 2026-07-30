# TrustLens API image.
#
# Deliberately WITHOUT the ML stack (ADR-0003): ~200 MB instead of ~2.5 GB,
# which is what keeps cold starts fast and lets the API scale independently of
# the AI pipeline. The `api-has-no-ml-deps` import-linter contract fails CI if
# anything reintroduces torch or opencv here.

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependency layer first, so a source change does not re-resolve everything.
COPY pyproject.toml uv.lock* ./
COPY packages/py/trustlens-core/pyproject.toml   packages/py/trustlens-core/
COPY packages/py/trustlens-shared/pyproject.toml packages/py/trustlens-shared/
COPY packages/py/trustlens-db/pyproject.toml     packages/py/trustlens-db/
COPY apps/api/pyproject.toml                     apps/api/
RUN uv sync --frozen --no-dev --package trustlens-api --no-install-project || \
    uv sync --no-dev --package trustlens-api --no-install-project

COPY packages/py/trustlens-core   packages/py/trustlens-core
COPY packages/py/trustlens-shared packages/py/trustlens-shared
COPY packages/py/trustlens-db     packages/py/trustlens-db
COPY apps/api                     apps/api
COPY database                     database
RUN uv sync --no-dev --package trustlens-api

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 trustlens

COPY --from=builder --chown=trustlens:trustlens /app /app
USER trustlens

EXPOSE 8000
# Liveness only: a readiness check here would restart the container whenever
# Redis hiccups, turning a blip into an outage.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/live || exit 1

CMD ["sh", "-c", "uvicorn trustlens_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --no-server-header"]
