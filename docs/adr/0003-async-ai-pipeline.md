# ADR-0003: AI processing runs in a separate worker process, not in the API

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Haseeb Ur Rehman, Muhammad Muttayab

## Context

CNIC OCR (OpenCV + EasyOCR), face matching (DeepFace), and LLM listing analysis take seconds to tens of
seconds and pull in heavy native and ML dependencies (torch, tensorflow, opencv) totalling ~2–3 GB.

The proposal's stated outcome is a system that returns an explainable score *"within seconds"*, and the
backend deploys to Railway, where container memory and cold-start time are real constraints.

## Decision

- `apps/api` (FastAPI) stays thin: validation, auth, persistence, enqueue. No ML dependencies. ~200 MB image.
- `apps/worker` (ARQ over the Redis the proposal already mandates) runs all AI work. ~2.5 GB image.
- Upload endpoints return **202 + job id**; the client polls `GET /api/v1/jobs/{id}`.
- Score *reads* are sub-100 ms because the score is precomputed and Redis-cached.
- The API enqueues jobs **by name**, never by importing worker functions — otherwise the import graph
  would drag torch back into the API and silently undo this decision.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **Synchronous processing in the request** | 30-second HTTP requests, proxy timeouts, no retry, no progress feedback, and the API image inflated to 3 GB |
| **FastAPI `BackgroundTasks`** | Work dies with the process, cannot be retried, cannot be observed, and cannot be scaled independently. Unacceptable when the outcome determines someone's trust score |
| **Celery** | Works, and is more widely known, but is sync-first (mismatched with FastAPI's async stack) and carries substantially more configuration surface |
| **Serverless functions for AI** | Cold starts with multi-GB ML images are pathological; also splits deployment across a third platform |
| **One container running both API and worker** | Couples scaling profiles, inflates every API replica by 2 GB, and makes an API deploy risk the AI pipeline |

## Consequences

**Positive**
- Fast, small, cheap API; independent scaling of AI capacity.
- Retries, backoff, dead-lettering, and progress reporting come free with a real queue.
- A worker crash (a malformed image killing OpenCV) cannot take down the API.
- Meets the "within seconds" outcome honestly: the *read* is instant, the computation happens once, in
  the background, when evidence changes.

**Negative / accepted costs**
- Eventual consistency: the UI must handle "processing" states, and the frontend needs polling logic.
- Two deployables, two Dockerfiles, two sets of env vars.
- Job state must be mirrored to Postgres (`job_runs`) so the UI can query it — Redis alone would lose it.

**Revisit if:** inference becomes fast enough (a small local model, or a sub-second hosted API) that
synchronous processing fits comfortably inside a request budget — unlikely for DeepFace and EasyOCR.
