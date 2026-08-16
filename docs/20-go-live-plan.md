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
| Image    | ~2.5 GB                 | **1.16 GB measured** (predicted 400-500 MB) |
| RAM      | ~2 GB                   | **323 MB measured**, both engines resident  |
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

### Step 1 — Fix the worker's Redis death (P9-09) · ½ day ✅ done 13 Aug

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

### Step 2 — Contract tests for the AI ports · ½ day ✅ done 13 Aug

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

### Step 3 — ONNX adapters · 1 day ✅ done 13 Aug

- `ocr/rapidocr_engine.py` and `face/insightface_matcher.py`, both implementing
  the existing ports.
- An `onnx` extra in `trustlens-ai`. `ml` is **kept**, so Phase 1 can benchmark
  the two against each other on real CNICs.
- Selected by `OCR_ENGINE` and `FACE_ENGINE`, both `Literal`-typed so a typo in
  an env var fails at startup rather than silently falling through to the heavy
  engine.

**Measured, not assumed.** Installed into a scratch environment and run:

|                        | Result                                                                    |
| ---------------------- | ------------------------------------------------------------------------- |
| ONNX OCR stack on disk | **233 MB** (against ~800 MB for PyTorch alone)                            |
| Real inference         | read a generated CNIC at **0.995 confidence**, parsed the number and name |
| Bad input              | zero confidence, no exception, on garbage / empty / 1px PNG               |
| Determinism            | identical bytes produce identical results                                 |
| Contract suite         | **41 passed** with both ONNX adapters auto-detected                       |

**Latency is the honest catch:** ~13 s to load the models once, then ~2 s per
document on a 12-core dev machine (1 thread ~2.6 s, 4 threads ~2.0 s, hence the
configurable `threads`). That is slow enough to matter, and it confirms rather
than changes the design: identity verification already returns `202 Accepted`
with a job id and is polled. On a free tier with a fraction of a core it will be
slower; the number for the report is the one measured on the deployed instance.

### Step 4 — Slim the worker image · ½ day

- Build against the `onnx` extra.
- Bake the model weights into the image rather than downloading at boot: a
  cold start that pulls 200 MB from a CDN is a cold start that fails when the
  CDN is slow, and free tiers cold-start often.
- Verify: image size, RSS at idle, and one real inference inside the container.

**Done when:** `docker images` shows under 600 MB and a job runs inside it.

**Done 17 Aug - and the target was missed.** The image is **1.16 GB**, not the
400-500 MB predicted above. That estimate was wrong by roughly 2.5x, and it is
left in the table rather than quietly corrected, because the gap is the point:
the ONNX _runtime_ is small, but InsightFace drags the scientific Python stack
behind it, and none of that was in the estimate.

What was actually removed, measured against the built image:

|               | Before  | After       |
| ------------- | ------- | ----------- |
| Image         | 1.56 GB | **1.16 GB** |
| Baked models  | 281 MB  | **16 MB**   |
| OpenCV copies | 2       | **1**       |

Two defects found by building rather than reasoning:

- **The worker image had never built, once, ever.** The root `pyproject.toml`
  declares `trustlens-api` a workspace member, but the Dockerfile copied only
  `apps/worker/`, so `uv sync` refused to resolve. CI never built it either, so
  nothing said so. Deployment would have been the first attempt.
- **265 MB of the 281 MB of baked weights was never opened.** InsightFace keeps
  the downloaded zip _and_ the unpacked bundle, and `allowed_modules` governs
  what loads, not what downloads. A 137 MB 3D-landmark model this adapter
  explicitly excludes was being shipped. Detection and recognition are 15 MB.

What remains is irreducible without dropping InsightFace: scipy 109 MB, onnx
85 MB, opencv-headless 153 MB, onnxruntime 58 MB, sklearn 49 MB, numpy 43 MB.

**The number that decides hosting is RAM, not image size: 323 MB peak** with
both engines resident. That does not fit a 256 MB free instance, so the worker
needs a 512 MB one - roughly $3-4/month on Fly.io. Everything else in Step 5
still fits a free tier.

Verified inside the container: real OCR reads a generated CNIC at 0.996
confidence with the number parsed correctly, and both engines load from baked
weights with no network access.

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
