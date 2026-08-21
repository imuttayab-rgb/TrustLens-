# TrustLens worker image.
#
# Carries the ML stack the API must never have (ADR-0003). Built against the
# `onnx` extra rather than `ml`: RapidOCR and InsightFace run the same class of
# model through onnxruntime instead of PyTorch and TensorFlow, which is the
# difference between ~2.5 GB and something a free tier will host.
#
# Build the legacy stack instead with `--build-arg AI_EXTRA=ml` - Phase 1 needs
# both to benchmark them against real CNICs (P1-01).

ARG AI_EXTRA=onnx

FROM python:3.12-slim AS builder
ARG AI_EXTRA
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Build-time system libs for the native wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./
COPY packages/py/ packages/py/
COPY apps/worker/ apps/worker/
# The API's manifest, not its source. The root pyproject declares every app as
# a uv workspace member, and uv refuses to resolve when a declared member is
# absent - so a worker image that copies only apps/worker/ cannot build at all.
# This copies the one file uv needs to see the member exists, which keeps the
# API's code out of the worker image (ADR-0003: the API must never carry the ML
# stack, and the worker has no reason to carry the API).
COPY apps/api/pyproject.toml apps/api/pyproject.toml
# Same reason, added later: apps/ml is a workspace member too. It holds the
# training code, which must never ship (the `nothing-imports-training-code`
# contract), so only its manifest comes across.
COPY apps/ml/pyproject.toml apps/ml/pyproject.toml
RUN uv sync --no-dev --package trustlens-worker --extra "${AI_EXTRA}"

# ── Model weights, baked ───────────────────────────────────────────────
#
# InsightFace downloads its weights on first use. Left alone, the first
# verification after a deploy is a several-hundred-megabyte fetch: on a free
# tier that cold-starts, that is a job which times out rather than one which is
# slow - and it fails for a seller, not for us. So the download happens here,
# once, at build time.
#
# RapidOCR ships its ONNX models inside the wheel, so it needs nothing.
FROM builder AS models
ARG AI_EXTRA
ENV PATH="/app/.venv/bin:$PATH" INSIGHTFACE_HOME=/app/models
RUN mkdir -p /app/models && \
    if [ "${AI_EXTRA}" = "onnx" ]; then \
      python -c "\
import os; from insightface.app import FaceAnalysis; \
app = FaceAnalysis(name=os.environ.get('FACE_ONNX_MODEL', 'buffalo_s'), \
                   root='/app/models', \
                   allowed_modules=['detection', 'recognition'], \
                   providers=['CPUExecutionProvider']); \
app.prepare(ctx_id=-1, det_size=(640, 640)); \
print('insightface weights cached')" && \
      # InsightFace downloads the whole bundle as a zip and unpacks it, keeping
      # both. `allowed_modules` decides what gets *loaded*, not what gets
      # *fetched*, so the image otherwise carries 265 MB it will never open:
      # the 122 MB zip, and 143 MB of landmark and age/gender models this
      # adapter explicitly excludes. Detection and recognition are 15 MB.
      find /app/models -name '*.zip' -delete && \
      find /app/models -name '1k3d68.onnx' -delete && \
      find /app/models -name '2d106det.onnx' -delete && \
      find /app/models -name 'genderage.onnx' -delete && \
      du -sh /app/models; \
    fi

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Where the baked weights live. The adapter reads this rather than
    # defaulting to ~/.insightface, so the image and a local checkout share one
    # code path.
    INSIGHTFACE_HOME=/app/models \
    DEEPFACE_HOME=/home/trustlens

# Runtime GL libs that OpenCV links against. Missing these is the classic
# "ImportError: libGL.so.1" on a slim base image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 trustlens

COPY --from=models --chown=trustlens:trustlens /app /app
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
