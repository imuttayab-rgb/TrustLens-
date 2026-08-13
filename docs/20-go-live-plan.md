# Go-live plan — real AI on a free tier

**Decided 12 August 2026.** Goal: the whole system running on public URLs, with
**real** OCR and face matching, at **$0/month**.

The blocker is not the architecture. It is two Python libraries.

---

## Why this is a library change, not an architecture change

`factory.py` is the single place that chooses which AI adapter is built, and
every heavy import happens **lazily inside a branch**. That is deliberate
(ADR-0003, enforced by the `api-has-no-ml-deps` import-linter contract), and it
means a new adapter is:

- one new file implementing the existing `OcrEngine` / `FaceMatcher` port,
- one branch in `factory.py`.

Nothing in the domain, the use cases, the API, the database or the frontend
changes. The ports already define the contract:

```python
class OcrEngine(Protocol):
    async def extract(self, image: bytes, *, document_type: str) -> OcrResult: ...

class FaceMatcher(Protocol):
    async def compare(self, document: bytes, selfie: bytes) -> FaceMatchResult: ...
```

## The actual problem

| Current library         | What it drags in | Size    |
| ----------------------- | ---------------- | ------- |
| `easyocr`               | PyTorch          | ~800 MB |
| `deepface` + `tf-keras` | TensorFlow       | ~600 MB |

Both are **wrappers**. The models underneath are small; the frameworks are not.
A ~2.5 GB worker image needs ~2 GB RAM at rest, which no free tier offers.

## The swap

|          | Now                     | After                                       |
| -------- | ----------------------- | ------------------------------------------- |
| OCR      | `easyocr` (PyTorch)     | **RapidOCR** (`onnxruntime`)                |
| Face     | `deepface` (TensorFlow) | **InsightFace `buffalo_s`** (`onnxruntime`) |
| Image    | ~2.5 GB                 | **~400–500 MB**                             |
| RAM      | ~2 GB                   | **~400 MB**                                 |
| Accuracy | unmeasured              | unmeasured — _both_ benchmarked in Phase 1  |

**This is not a downgrade to fakes.** Same neural networks, lighter runtime.
InsightFace's ArcFace is what DeepFace wraps in the first place; RapidOCR is
PaddleOCR's models exported to ONNX.

### The honest caveat

Neither the current adapters nor the new ones have **ever run on a real CNIC
image** — P1-01 and P1-06 are still blocked on collecting them. So the new
adapter cannot be "worse than what works", because nothing has been shown to
work yet.

That is why both stay in the tree behind a setting. When the images arrive,
**both get benchmarked** and the numbers go in the report. "We compared two
approaches and chose on measured accuracy" is a better methodology section than
"we picked one".

---

## Order of work

Each step is independently verifiable and independently committable.

### Step 1 — Fix the worker's Redis death (P9-09) · ½ day

**Why first:** it blocks deployment, and it is small.

Both worker processes exited with `ConnectionError` when the dev containers
stopped, and neither came back. Locally that looked environmental. On Upstash it
is routine — **idle connections are closed by design** — so without this fix the
worker stops consuming silently: no OCR, no face match, no email, no OTP, no
rescoring, and nothing announces it.

- Retry/reconnect around the ARQ event loop with bounded backoff.
- `restart: unless-stopped` in compose, and the platform equivalent in Fly.
- A health signal that fails when the worker is not consuming (pairs with P9-07).

**Done when:** stop Redis, start it again, and the worker resumes consuming
without a human touching it.

### Step 2 — Contract tests for the AI ports · ½ day

**Written before the new adapters, not after.** One suite that any `OcrEngine`
or `FaceMatcher` must pass — fake, easyocr/deepface, and the ONNX pair all run
against the same cases:

- returns the declared dataclass with a confidence in `[0, 1]`,
- garbage bytes produce a low-confidence result, never an exception that
  escapes the adapter,
- an image with no detectable face sets `face_detected_*` false rather than
  raising,
- `engine` and `engine_version` are populated — the report has to say which
  model produced which number.

Without this, swapping adapters is "it seems to work". With it, the swap is
proved.

### Step 3 — ONNX adapters · 1 day

- `ocr/rapidocr_engine.py` implementing `OcrEngine`.
- `face/insightface_matcher.py` implementing `FaceMatcher`.
- A new `onnx` extra in `trustlens-ai`; `ml` stays so the old path remains
  runnable for the Phase 1 comparison.
- `factory.py` picks by `AI_ENGINE=onnx|legacy|fake`.

The existing `ml` extra is **not deleted**. Phase 1 needs both to benchmark.

### Step 4 — Slim the worker image · ½ day

- Build against the `onnx` extra.
- Bake the model weights into the image rather than downloading at boot: a
  cold start that pulls 200 MB from a CDN is a cold start that fails when the
  CDN is slow, and free tiers cold-start often.
- Verify: image size, RSS at idle, and one real inference inside the container.

**Done when:** `docker images` shows under 600 MB and a job runs inside it.

### Step 5 — Deploy · 1 day

| Piece      | Host              | Free tier     | Watch out for                        |
| ---------- | ----------------- | ------------- | ------------------------------------ |
| web, admin | **Vercel**        | Hobby         | —                                    |
| api        | **Fly.io**        | shared-cpu-1x | ~200 MB image, fits easily           |
| worker     | **Fly.io**        | shared-cpu-1x | needs Step 4 first                   |
| Postgres   | **Neon**          | 0.5 GB        | **sleeps after 5 min idle**          |
| Redis      | **Upstash**       | 10k cmd/day   | **closes idle connections** → Step 1 |
| Storage    | **Cloudflare R2** | 10 GB         | egress free                          |
| Email      | **Resend**        | 3k/month      | needs a domain for SPF/DKIM/DMARC    |
| Errors     | **Sentry**        | 5k events     | fills the empty `shared/telemetry/`  |

Two rough edges to plan for rather than discover:

- **Neon sleeps.** First request after idle takes 3–5 seconds. Ping it before a
  demo. Do not let the examiner's first click be the wake-up call.
- **Free tiers cold-start.** The worker waking on the first job is normal;
  baking the weights (Step 4) is what keeps that from being 60 seconds.

### Step 6 — Prove it end to end on the deployed system · ½ day

Not "it deployed". The same journeys, run against the public URLs: register →
verify email → become seller → upload CNIC → score computed by the **real**
engine → public page renders → partner key reads a signed score → webhook fires.

---

## What this does not fix

- **P0-12** — the public buyer page still 404s because `apps/web` holds no API
  key. Unblocked, undecided. It is the screen the demo opens on.
- **P1-01 / P1-06** — still no real CNIC or face images, so still no accuracy
  numbers. Nothing here substitutes for collecting them.
- **Phase 7** — the scam classifier is separate work; it benefits from the ONNX
  runtime already being present.

---

## Cost

**$0/month.** The only paid alternative considered was a ~$5/month VPS to carry
the 2.5 GB image unchanged. Step 3 removes that need, and leaves the system
lighter for the examiner to run afterwards.
