# TrustLens worker image.
#
# Carries the full ML stack (opencv, easyocr, deepface) that the API must never
# have. Larger and slower to build on purpose - it is deployed independently
# and scales on queue depth rather than request rate.

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Build-time system libs for the native wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./
COPY packages/py/ packages/py/
COPY apps/worker/ apps/worker/
RUN uv sync --no-dev --package trustlens-worker --extra ml

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DEEPFACE_HOME=/home/trustlens

# Runtime GL libs that OpenCV links against. Missing these is the classic
# "ImportError: libGL.so.1" on a slim base image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 trustlens

COPY --from=builder --chown=trustlens:trustlens /app /app
USER trustlens

# The supervisor handles SIGTERM: it stops retrying and lets the worker finish
# the current job before exiting. Jobs are idempotent, so a killed job is
# safely retried.
#
# Runs the supervisor rather than `arq` directly, because arq returns when
# Redis drops and PID 1 returning means the queue silently stops being
# consumed. Upstash closes idle connections by design (P9-09).
STOPSIGNAL SIGTERM
CMD ["python", "-m", "trustlens_worker.supervisor"]
