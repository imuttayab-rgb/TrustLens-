# Real OCR + CNIC expiry check (FYP pilot)

Status: opt-in pilot, off by default (`OCR_REAL_IN_DEMO=false`).

## What it does

With `OCR_REAL_IN_DEMO=true`, the worker uses the local, free RapidOCR
(ONNX) engine on the live-captured CNIC images. The LLM and the scam
classifier stay on their offline stand-ins (`USE_FAKE_AI=true`), so no paid
API key is needed. Real face matching remains controlled separately by
`FACE_MATCH_REAL_IN_DEMO`.

1. The front of the card is read. The back is read too, because the expiry
   may be printed on either side depending on the card generation.
2. The two readings are combined (`apps/worker/src/trustlens_worker/jobs/cnic_reading.py`).
3. The expiry date is **enforced automatically only when it is reliable**:
   - birth, issue and expiry dates were all found (the parser never treats an
     issue date as an expiry);
   - mean OCR confidence >= 0.70 and image quality >= 0.25;
   - front and back do not disagree on the CNIC number or the expiry;
   - the issue-to-expiry span is plausible (4-16 years), which catches
     common single-digit year mis-reads.
4. Outcomes:

| Situation | Result |
| --- | --- |
| Reliable expiry in the past | Rejected automatically: "The submitted ID has expired." |
| Reliable expiry in the future | Continues to face match / hold-ID review as before |
| Expiry missing, unclear, conflicting or implausible | Manual review with a reason code (`CNIC_EXPIRY_UNREADABLE`, `CNIC_EXPIRY_LOW_CONFIDENCE`, `CNIC_EXPIRY_CONFLICT`, `CNIC_EXPIRY_IMPLAUSIBLE`, `CNIC_SIDES_DISAGREE`) |
| Fake OCR (flag off) | Unchanged: simulated values are never enforced; manual review |

The CNIC duplicate-account index is created only from a structurally valid
number that both sides agree on, so an OCR mis-read cannot create a false
"duplicate account". When a reviewer approves a case, the CNIC front document
is marked verified so a genuine card that OCR could not read does not keep
lowering the seller's score.

## After verification: the card expires later

A card valid on submission day eventually expires. Two backend rules cover
this (no UI change, no migration; `EXPIRED` already exists in the
`verification_status` enum):

1. **Daily expiry sweep** (`identity.expire_lapsed`, worker cron at 02:30 and
   once at worker startup, so a laptop that was off still catches up).
   A `VERIFIED` seller whose real-OCR expiry date has passed becomes
   `EXPIRED`. In the same transaction the publication gate moves their
   `ACTIVE` listings back to private `DRAFT` (sold/reserved/flagged listings
   are untouched), an audit entry `identity.document_expired` is written
   with status values only, and a trust-score recompute is queued. The seller
   can resubmit with a renewed card (`StartIdentityVerification` only blocks
   `PROCESSING` and `VERIFIED`).
2. **Reviewer guard**: a reviewer cannot approve an identity case whose
   real-OCR expiry has passed (`InvalidStateError`, HTTP 422). They reject it
   so the seller can resubmit.

Evidence rules (`trustlens.core.application.services.identity_expiry`):

- Only documents from a real OCR engine count; `fake` and `demo` engines
  (the fake adapter and the seed data) can never revoke anyone.
- Only the CNIC sides linked to the seller's **latest** verification count,
  so an expired card from an older, superseded submission is ignored.
- A card is valid through its printed expiry date (`expiry < today`).
- In real-OCR mode the worker only stores an expiry that was read reliably
  (see above), so the sweep never acts on an unclear reading.

## What it does NOT do

- It does not prove a card is genuine. There is no NADRA/government record
  check; a well-made fake card with a future date will read as "valid".
- It is not certified liveness or presentation-attack detection.
- Accuracy on real Pakistani CNICs has **not** been benchmarked. The
  automated tests use synthetic, computer-drawn cards only. A real accuracy
  figure needs a consented, labelled test set (P1-01) before any claim.
- Phone/laptop camera quality, glare and motion directly affect results;
  unclear images go to a human rather than being rejected.

## Privacy

The CNIC number is stored envelope-encrypted, only a blind index is used for
duplicates, and logs record the expiry *status* only, never the date, number
or name. All biometric/identity media keeps the existing retention policy.

## Operations

- Enable: `OCR_REAL_IN_DEMO=true` (and `OCR_ENGINE=rapidocr`) in
  `.env.production`, rebuild/recreate `api` and `worker`.
- Disable: set `OCR_REAL_IN_DEMO=false` and recreate `api` and `worker`
  with `--no-build`; behaviour returns to the previous fake-OCR mode.
- Identity jobs use `WORKER_JOB_IDENTITY_TIMEOUT_SECONDS` (default 300 s)
  because two OCR passes plus face matching run on a CPU-only laptop.

## Tests

- `apps/worker/tests/test_cnic_real_ocr.py` - parser rules, side combination,
  and the real engine on synthetic valid / expired / missing / blurred cards.
- `apps/worker/tests/test_identity_real_ocr_job.py` - the full identity job
  with the real engine: valid -> verified, expired -> rejected, missing expiry
  -> manual review, blurred -> manual review, fake OCR -> never rejected.
- `packages/py/trustlens-core/tests/application/test_review_approval_document.py`
  - reviewer approval clears an unreadable front document.
- `packages/py/trustlens-ai/tests/test_factory_selection.py` - the flag
  enables only real OCR and defaults off.
- `packages/py/trustlens-core/tests/application/test_identity_expiry_sweep.py`
  - evidence rules (fake/demo/superseded ignored, valid through expiry day),
  the sweep (revoke, hide ACTIVE only, audit without the date, rescore,
  idempotent) and the reviewer guard.
- Verified in the sandbox against PostgreSQL 16 with all Alembic migrations
  applied: only the real-OCR expired seller was revoked; fake, demo, future
  and superseded cases stayed `VERIFIED` with listings `ACTIVE`.
