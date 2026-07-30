# 14 — Testing Strategy

## 1. Shape of the suite

```
        ▲  E2E (Playwright)                ~25 specs      slow, high confidence
       ╱ ╲   critical journeys only
      ╱   ╲ Contract (Schemathesis) + API (httpx)   ~60    the API's real behaviour
     ╱     ╲
    ╱       ╲ Integration (testcontainers)          ~150   repositories, jobs, adapters
   ╱         ╲
  ╱___________╲ Unit (pytest + vitest)              ~500   domain, policies, components
```

Coverage gates: **80% overall**, **95% on `packages/py/trustlens-core`**. The domain package holds the
scoring rules — the part of the system that decides whether a real person is labelled a fraud risk. It
is pure, fast to test, and has no excuse for gaps.

Coverage is a floor, not a goal. A 100%-covered `scoring_policy` that was never tested with an
`UNAVAILABLE` signal is worse than 80% with that case covered.

## 2. Unit tests

**Backend** — `pytest`, no I/O, no database, no network. Every dependency is a fake from
`packages/py/trustlens-testing`.

Highest-value targets:

| Target | Cases that must exist |
|---|---|
| `scoring_policy` | All PASS → 100 · all FAIL → 0 · `UNAVAILABLE` excluded from the denominator · hard cap applied on each critical failure · `available_weight < MIN` → `UNKNOWN` · rounding at band boundaries (39/40, 69/70) · weights that don't sum to 100 → error |
| `risk_band_policy` | Exact boundary values, not just midpoints |
| `freshness_policy` | Frozen clock at `valid_until` ± 1 s |
| `device_linkage_policy` | 1, 2, 3, 10 accounts per device |
| Value objects | `CnicNumber` format/checksum, `PhoneE164` normalisation, `Score` clamping, `Email` case folding |
| Use cases | Happy path, each failure branch, event published, transaction rolled back on error |

```python
def test_unavailable_signal_is_excluded_from_denominator():
    signals = [passed("IDENTITY_FACE_MATCH", 15), unavailable("LISTING_CONTENT_SAFE", 10)]
    result = policy.evaluate(signals)
    assert result.available_weight == 15
    assert result.score == 100  # not 60 — our outage must not penalise the seller
```

**Frontend** — Vitest + React Testing Library. Test behaviour, never implementation:

- `ScoreGauge` renders the right band colour **and** the band text at 39, 40, 69, 70
- `SignalBreakdown` orders reasons by point impact
- `RiskBadge` never renders `UNKNOWN` in green or red
- `OtpInput` handles paste, backspace, and auto-advance
- `useJobStatus` stops polling on a terminal status
- Zod schemas accept valid and reject invalid input at boundaries

MSW mocks the API at the network layer so components are tested against realistic responses rather than
hand-stubbed hooks.

## 3. Integration tests

`testcontainers` spins up **real** Postgres and Redis per session. Not SQLite, not mocks — the schema
uses Postgres enums, partial unique indexes, `citext`, `inet`, `JSONB`, and partitioning, none of which
SQLite models. A test suite that passes on SQLite and fails on Postgres has tested nothing useful.

| Area | What is verified |
|---|---|
| Repositories | Real SQL round-trips, entity↔row mapping, soft-delete filtering, `deleted_at` partial-unique behaviour |
| Constraints | `uq_trust_scores_current` really prevents two current scores; the override-reason CHECK really fires |
| Migrations | Fresh DB → `upgrade head` → `downgrade base` → `upgrade head` with no error |
| Transactions | A failing use case rolls back every write, including the outbox row |
| Jobs | Enqueue → worker executes → DB state changes → cache invalidated |
| Cache | Cache-aside hit/miss/invalidate paths against real Redis |
| Rate limiting | Token bucket refills correctly across a simulated clock |
| Adapters | Each real adapter passes the **same port contract suite** as its fake |

The port contract suite is the mechanism that keeps fakes honest: `FakeOcrEngine` and `EasyOcrEngine` both
run `OcrEngineContractTests`, so a unit test written against the fake means something about production.

## 4. API tests

`httpx.AsyncClient` against the ASGI app with a real database:

- Auth: register → verify email → login → refresh → rotation → **reuse detection revokes the family**
- AuthZ: each role against each endpoint, asserting 200/403 per the [09](09-user-roles.md) matrix —
  generated from the matrix so a new endpoint without an entry fails the test
- **IDOR:** seller A cannot read seller B's listing, appeal, identity document, or full score breakdown.
  One parametrised test over every resource-scoped endpoint
- Validation: bad payloads → 422 with the right `code` and `errors[].field`
- Pagination/filter/sort: page bounds, unsortable field → 422, cursor stability under concurrent inserts
- Idempotency: same key + same body → replayed response; same key + different body → 422
- Rate limits: 429 with `Retry-After` and correct `X-RateLimit-*`
- Public API: valid key, revoked key (410), wrong scope (403), quota exceeded (429), and **no PII in any
  public response** — asserted by scanning the payload for forbidden keys

That last assertion is a structural guard: a future developer adding `email` to a public schema breaks a
test rather than leaking data.

## 5. Contract tests

**Schemathesis** fuzzes every endpoint from the live OpenAPI document: property-based inputs, checks that
responses conform to the declared schemas, no undeclared 500s, correct status codes. It routinely finds
the cases nobody writes by hand — empty strings, huge integers, unicode in names, null where optional.

**OpenAPI diff** (`tools/openapi`) compares the PR's spec against `main` and fails on a breaking change to
`/public/v1` without a version bump. Partners depend on that surface; breaking it silently is not
recoverable by a redeploy.

## 6. AI / ML evaluation

The AI components need a different kind of testing — they are probabilistic, so assertions are on
**aggregate metrics**, not individual outputs.

| Component | Test |
|---|---|
| OCR (`EasyOcrEngine`) | A fixture set of **synthetic** CNIC images (clean, blurred, rotated, glared). Assert field-extraction accuracy ≥ threshold, not exact strings |
| Face match (`DeepFaceMatcher`) | Labelled same-person / different-person pairs from a public research dataset. Assert TPR/FPR at the configured threshold; assert the borderline band routes to manual review |
| LLM analyzer | Recorded fixtures (VCR-style) for determinism in CI; a separate nightly job hits the live API and asserts structured-output schema conformance and label stability |
| Scam classifier | Held-out test set; assert precision/recall ≥ the previous model version. **A model that regresses cannot be published** — the registry check is part of `apps/ml` CI |
| Prompt changes | Golden-set regression: 50 labelled listings, assert agreement with expected labels ≥ baseline |

All ML fixtures are synthetic or from public research datasets. **No real CNIC images ever enter the
repository** ([10 §8](10-folder-structure.md)).

Fairness slices are part of the evaluation report, not an afterthought: per-slice FPR for the face
matcher, since a demographic disparity there becomes a demographic disparity in who gets labelled
high-risk ([08 §9](08-trust-score-engine.md)).

## 7. E2E tests

Playwright, Chromium + WebKit, against a full Docker Compose stack with `USE_FAKE_AI=true` (deterministic,
fast, no keys, no cost).

| Spec | Journey |
|---|---|
| `auth.spec.ts` | Register → verify email (via MailHog API) → login → logout |
| `seller-verification.spec.ts` | Upload CNIC + selfie → job progress → confirm OCR fields → phone OTP → email → checklist complete |
| `trust-score.spec.ts` | Score appears, breakdown expands, improvement list is ranked, history chart renders |
| `public-score-page.spec.ts` | Anonymous visitor loads `/seller/{handle}`, sees score + reasons, no PII rendered |
| `appeals.spec.ts` | Seller appeals → reviewer sees the case → resolves → seller is notified → score recomputed |
| `admin-scoring.spec.ts` | Admin edits weights → simulates → sees the distribution delta → activates → scores recompute |
| `public-api.spec.ts` | Create client + key in admin → call `/public/v1` with it → revoke → 410 |
| `rbac.spec.ts` | A seller hitting `/admin` gets 403; a reviewer cannot see the scoring-model editor |
| `a11y.spec.ts` | axe-core scan on every key page — zero critical violations |

Rules: E2E tests use `data-testid`, never CSS classes or text (both change constantly); each test seeds
its own data and cleans up; no test depends on another's ordering; retries are capped at 1 so genuine
flakiness surfaces instead of being masked.

## 8. Load tests

k6, run before the final demo and before any public-API launch:

| Scenario | Target |
|---|---|
| `GET /public/v1/sellers/{ref}/trust-score` — 100 VUs, 5 min | p95 < 150 ms, error rate < 0.1% |
| Cache-miss storm — 100 VUs on 100 distinct sellers | p95 < 500 ms, no connection-pool exhaustion |
| Login — 50 VUs | p95 < 400 ms (argon2 is intentionally slow; this validates the parameter choice) |
| Upload intent — 20 VUs | p95 < 200 ms |
| Job throughput — 200 identity jobs queued | Queue drains; no OOM in the worker |

The argon2 scenario matters: memory-hard hashing is a deliberate CPU cost, and load testing is how you
discover that your parameters make login a DoS vector on a small Railway instance.

## 9. Security tests

- OWASP ZAP baseline scan against staging in CI (nightly)
- `pnpm audit` + `pip-audit` on every PR; Trivy on built images
- `gitleaks` in pre-commit and in CI history scans
- Automated authz matrix test (§4) — the highest-yield security test in a role-based system
- Manual review per [15](15-security.md) before the final submission

## 10. Test data & fixtures

| Kind | Source |
|---|---|
| Users/sellers | `factory-boy` factories in `trustlens-testing` |
| CNIC images | **Generated synthetic** cards with fake names and numbers (`scripts/gen-test-cnic.py`) |
| Selfies | Public consented face datasets, or generated faces |
| Listings | A hand-labelled scam/genuine corpus in `apps/ml/data/labels/` |
| API responses | VCR cassettes with keys and PII scrubbed |

Never in fixtures: real CNIC numbers, real names, real phone numbers, real email addresses, live API keys.

## 11. Local vs CI

| Command | Duration | When |
|---|---|---|
| `make test-unit` | < 30 s | Every save (watch mode) |
| `make test` | ~3 min | Before pushing (pre-push runs the unit subset) |
| `make test-e2e` | ~5 min | Before opening a PR against `main` |
| Full CI | ~8 min | Every PR |
| Nightly | ~25 min | E2E on both browsers, ZAP, live-LLM contract check, load smoke |
