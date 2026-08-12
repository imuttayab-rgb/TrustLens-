# TrustLens — Implementation Plan & Task Tracker

**Project:** TrustLens – AI-Powered Seller Trust Verification System
**Clients:** Haseeb Ur Rehman (2022F-mulbsswe-043), Muhammad Muttayab (2022F-mulbsswe-012)
**Supervisor:** Mam Misbha — School of Software Engineering

---

## Scope decision — academic FYP

**Confirmed 31 July 2026: TrustLens is delivered as an academic Final Year Project, not a commercial product.**

Three consequences, and they save real time:

| Issue                                                                                               | Because it is academic                                                                                                                                                                                      |
| --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Face model licences** — InsightFace/ArcFace pretrained weights are _non-commercial research only_ | ✅ Permitted. Academic research is exactly the allowed use. **Still document the licence position in the report** (P7-08) — examiners respect it, and it protects the students if they commercialise later. |
| **SMS OTP** — Pakistan requires PTA + per-carrier sender ID registration with an NTN                | ✅ Not required. SMS stays **demo-scale only** via a Twilio trial. Email OTP is the primary channel. Documented as a deployment constraint, not a defect.                                                   |
| **Commercial SaaS concerns** — scam-report feedback loop, liability terms, paid-tier scaling        | ✅ Moved to the **Future Scope** chapter of their report, where the proposal already places them.                                                                                                           |

**What this does _not_ excuse:** the system must still work on a phone, emails must still arrive, and the students must still be able to run it after handover. Those are in scope.

---

## How to use this file

- One **Phase** = a coherent chunk of work. One **Day** = one focused working day (~5–6 hours).
- Tick a box the moment a task is genuinely done — not "written" but **runs and is verified**.
- Every task has a **Done when** line. If you cannot demonstrate that line, the box stays empty.
- Task IDs (`P2-04`) are stable. **Commitlint enforces a scope allow-list**, so the ID goes in the body, not the scope:
  `feat(verification): selfie capture screen` + a `Tasks: P2-04` line.
  Valid scopes: `web, admin, api, worker, ml, core, db, ai, shared, ui, auth, scoring, verification, listings, appeals, public-api, infra, docs, deps, release`. Subjects must be lower-case.
- Update the **Progress** table at the end of each day. That table is what you show the client.

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

---

## Progress

### Software track

| Phase | Title                                 | Days   | Status                                                      | Owner  |
| ----- | ------------------------------------- | ------ | ----------------------------------------------------------- | ------ |
| 0     | Make it run                           | 1      | `[x]` **complete** — P0-09 and P0-11 both closed            | Zohaib |
| 1     | Prove the risky parts                 | 2      | `[~]` code done; **blocked on real CNIC/face images**       | Zohaib |
| 2     | Seller verification UI (mobile-first) | 8      | `[~]` onboarding + all four flows done; score/account left  | Zohaib |
| 3     | Listings module                       | 4      | `[~]` lifecycle, API, price signal + UI done; images left   | Zohaib |
| 4     | Admin panel                           | 5      | `[~]` reviewer workflow works end to end; seller admin left | Zohaib |
| 5     | Appeals                               | 3      | `[x]` **complete** — full lifecycle, both UIs, e2e green    | Zohaib |
| 6     | Public marketplace API                | 3      | `[x]` **complete** — keys, signing, webhooks, screens, docs | Zohaib |
| 7     | ML scam classifier                    | 4      | `[ ]`                                                       |        |
| 8     | Real integrations                     | 4      | `[ ]`                                                       |        |
| 9     | Deployment                            | 3      | `[ ]`                                                       |        |
| 10    | QA & demo readiness                   | 4      | `[ ]`                                                       |        |
| 11    | Handover & training                   | 3      | `[ ]`                                                       |        |
|       | **Software total**                    | **44** |                                                             |        |

### Documentation track (runs in parallel — see Track D)

| Track | Title                     | Days | Status | Owner                          |
| ----- | ------------------------- | ---- | ------ | ------------------------------ |
| D     | FYP academic deliverables | 9    | `[ ]`  | **TBD — decide who owns this** |

**Grand total: 53 working days** ≈ 13 weeks at 4 days/week, or 10.5 weeks at 5 days/week.
Map to real dates once the submission date is confirmed.

---

## Current state (measured 31 July 2026)

What the scaffold commit `5185529` actually delivered:

| Area                                                         | State                                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------- |
| Domain + scoring engine                                      | ✅ Complete — all 14 signals implemented, 22 tests            |
| Database                                                     | ✅ 40 tables, migration + reference/demo seeds                |
| Auth (JWT + refresh rotation)                                | ✅ Complete                                                   |
| **Consent model incl. biometric consent gate**               | ✅ Complete — face match is blocked without versioned consent |
| Verification API (identity, phone, device)                   | ✅ Endpoints exist                                            |
| Trust score read/compute                                     | ✅ Complete                                                   |
| Public score endpoint                                        | ✅ Exists                                                     |
| Worker jobs + 3 cron schedules (incl. `purge_expired_media`) | ✅ Wired                                                      |
| CI (mypy, import-linter, coverage gate, codegen drift)       | ✅ Strong                                                     |
| AI adapters (OCR, face, LLM)                                 | 🟡 Written but **never run on real data**                     |
| Frontend                                                     | 🟡 ~890 lines — mostly placeholders, **no mobile layouts**    |
| Admin / Appeals / Listings / API-keys use cases              | ❌ **Empty folders**                                          |
| `apps/ml`                                                    | ❌ **Referenced but does not exist**                          |
| `shared/telemetry/`, `db/queries/`                           | ❌ Empty folders                                              |

**Status 31 July 2026:** the full stack has been installed and booted — Postgres/Redis/MinIO/Mailpit healthy, 41 tables migrated and seeded, API serving 32 endpoints, worker running 14 functions, web on :3000. Phase 0 is complete apart from P0-09 (broken Makefile targets) and P0-11 (91 mypy errors).

---

## Current state (measured 11 August 2026)

**Phase 0 is now genuinely complete**, and Phase 5 with it.

| Gate                | State                                    |
| ------------------- | ---------------------------------------- |
| `pytest`            | ✅ 219 passing                           |
| `mypy`              | ✅ clean — 144 files, 0 errors (was 91)  |
| `ruff` + `format`   | ✅ clean                                 |
| `tsc` web + admin   | ✅ clean                                 |
| `eslint` web +admin | ✅ clean                                 |
| Playwright          | ✅ appeal journey green across both apps |
| API surface         | 43 paths / 49 operations                 |

**What a user can now actually do, verified in a browser:** register → receive the email →
verify → sign in → create a seller profile → see the verification checklist → read an explainable
score with a capped-score explanation and ranked improvements → dispute it → have a reviewer claim,
decide, and trigger a recompute.

**Three defects found by testing the running system rather than reading the code.** All three
returned `200` to the caller while doing nothing:

1. The dashboard dead end (P2-04b) — the reported "nothing works". Auth was fine.
2. Two rescore jobs that never ran (P5-06), one of them since the Phase 4 review queue shipped.
3. `make codegen` pointing at a missing script (P0-09), so CI's drift guard had never passed.

**Still blocked and unchanged:** P1-01 / P1-06 need real CNIC and face images. Nothing in the
software track can substitute for them, and they gate the accuracy numbers the report needs (D-05).

---

# Phase 0 — Make it run (1 day)

**Goal:** every command in the Makefile works on your machine. Until this is true, nothing else is real.

### Day 1

- [x] **P0-01** Install prerequisites: Node 20+ (`.nvmrc`), Python 3.12 (`.python-version`), `pnpm`, `uv`, Docker Desktop.
      _Verified 31 Jul:_ Node 22.17.0, pnpm 9.12.3, uv 0.8.23, Docker 29.5.3, GNU Make 4.4.1. uv auto-pins Python 3.12, so the system's 3.13 is irrelevant.

- [x] **P0-02** Install dependencies (`pnpm install`, `uv sync --all-packages --dev`).
      _Verified 31 Jul:_ 205 Python packages, pnpm install clean in ~13 min.

  > ⚠️ The Makefile uses `SHELL := /bin/bash`. On Windows run it from **Git Bash**, not PowerShell.
  > ⚠️ Never run two `uv sync` commands at once — the second deadlocks on the cache lock and neither reports an error.

- [x] **P0-02b** Commit the missing lockfiles.
      _Done 31 Jul:_ `uv.lock` and `pnpm-lock.yaml` were untracked, so every install re-resolved the entire graph from scratch (~10 GB of downloads). Now committed — subsequent installs are cached and fast.

- [x] **P0-03** Start infrastructure: `make up`.
      _Verified 31 Jul:_ Postgres 16, Redis 7, MinIO and Mailpit all healthy.

- [x] **P0-04** Apply migrations and seed.
      _Verified 31 Jul:_ 41 tables (40 + `alembic_version`). Reference seed = 41 permissions, 4 roles, **14 signals, 14 weights**, 4 marketplaces. Demo seed = 6 users, 3 sellers, 3 listings, 3 scores.
      _Fixed on the way:_ Alembic read `os.environ` directly and never loaded the root `.env`, so `make migrate` failed on a correctly configured checkout. Secrets must also be generated first — run `bash scripts/generate-keys.sh` and paste the six values into `.env`, or seeding rejects the `CHANGEME` placeholders.

- [x] **P0-05** Boot the API.
      _Verified 31 Jul:_ **32 endpoints across 30 paths**. `/health/ready` → `database: ok, cache: ok`. `/public/v1/status` → scoring model `v1.0`.

  > Health lives at `/health/live` and `/health/ready` — **not** under `/api/v1/`.

- [x] **P0-06** Boot the worker.
      _Verified 31 Jul:_ registered **14 functions** (11 jobs + 3 cron), `fake_ai=True`, cron jobs executing.

  > On Windows the console throws `UnicodeEncodeError` on arq's `→`/`●` log characters. Cosmetic only — jobs complete normally. Set `PYTHONIOENCODING=utf-8` to silence it.

- [x] **P0-07** Boot the frontends.
      _Verified 31 Jul:_ web ready in 25 s; `/`, `/check`, `/login`, `/register` all return 200.
      _Fixed on the way:_ Next reads `.env` only from its own project directory, so neither app saw the root `.env`. `API_BASE_URL_INTERNAL` was `undefined`, so every server-rendered page fetched `undefined/public/v1/...`, hung 25 s and returned 500.

- [x] **P0-08** Run the quality gates: `make test-py`, `make lint`, `make check-arch`.
      _Verified 31 Jul:_ **75 tests pass** (22 original + 53 new), ruff clean across 162 files, format clean, import-linter **5/5 contracts kept**. `make typecheck` still fails — see P0-11.

- [x] **P0-08b** Fix the broken git hooks. _Three defects meant `git commit` could not succeed on any fresh clone:_
  - `lint-staged` called bare `ruff`, which lives in the uv venv and is not on PATH → now `uv run ruff`
  - `prettier-plugin-tailwindcss` was configured but installed nowhere → added to root devDependencies
  - No root `eslint.config.mjs`, and ESLint v9 treats a missing config as a hard error → added
    _Done when:_ `git commit` completes with hooks enabled. ✅

- [x] **P0-11** Clear the remaining **91 mypy errors** across 28 scaffold files.
      _Done 11 Aug:_ the tree typechecks clean — 144 source files, zero errors. The last two were
      `apps/ml/bench`, whose harnesses add their own `sys.path` root at runtime; mypy does not
      execute that, so `apps/ml` is declared in `mypy_path` instead.
      _Context:_ was 408. Adding PEP 561 `py.typed` markers to all six packages plus `mypy_path`/`explicit_package_bases` for the namespace layout fixed 317 of them. The rest are genuine gaps — mostly bare `dict` without type arguments and missing annotations in `middleware/`, `routers/auth.py`, `routers/verification.py`. None are in Phase 1 code.
      _Done when:_ `make typecheck` exits clean, so CI's mypy step can go green.

- [x] **P0-09** Fix the four **broken Makefile targets** — they reference files that were never created:
  - `make openapi` → works; exports 43 paths
  - `make postman` → `scripts/export-postman.sh` written; 10 tagged folders
  - `make erd` → `tools/erd/generate.py` renders all 40 tables as Mermaid (feeds **D-04**)
  - `make codegen` → `tools/codegen/generate.sh` was missing too, and this was the costly one:
    CI runs `make codegen` and fails on any diff, so the **codegen-drift job could not have passed
    on any PR since the scaffold**. The guard that makes a backend rename break the frontend build
    in the same PR (ADR-0005) was itself broken.
    _Done 11 Aug:_ all four run.

  > Mermaid rather than eralchemy/Graphviz for the ERD: no system package to install on a lab
  > machine during submission week, it renders inline on GitHub, and it pastes into the report.
  > Generated from the SQLAlchemy metadata, so it cannot drift from the schema it documents.

- [x] **P0-10** End-to-end smoke test with `USE_FAKE_AI=true`.
      _Verified 31 Jul:_ logged in as `seller.low@trustlens.dev` and read the authenticated score endpoint. **Score 25, risk HIGH, `capApplied: 25`** from the failed face match, confidence 0.85, and **all 14 signals returned with plain-English reasons** — "The selfie does not match the photo on the submitted ID", "This device is linked to several other seller accounts", "Prices are far below the normal range for similar items". The explainable Trust Score the proposal promises, working end to end.
      Demo sellers span all three bands: `ayesha-traders` 100/LOW, `bilal-motors` 77/MEDIUM, `quick-deals-pk` 25/HIGH.

- [x] **P0-13** 🚨 **Every background job was silently discarded.**
      _Found and fixed 31 Jul._ The domain enqueues by string (`identity.verify`, `notifications.send_email`, `contact.send_otp_sms`) because it must not import the worker (ADR-0003). ARQ registers a job under its Python function name unless told otherwise, so **none of the seven enqueued names matched** — Redis accepted each job and the worker dropped it with "function not found", with nothing surfacing to the caller.
      That means **OCR, face matching, verification emails, OTP SMS, IP enrichment, phone lookup and score recomputation had never run.** The demo data looked healthy only because the seed writes scores straight to the database.
      Fixed with `arq.func(..., name=...)` and pinned by `apps/worker/tests/test_job_names.py`, which scans every enqueue call site and fails when a name is unregistered. Verified: registering a user now delivers a confirmation email to Mailpit.

- [x] **P0-14** 🚨 **No authenticated page could ever render.**
      _Found and fixed 2 Aug._ `serverFetch` forwarded cookies and its docstring claimed a server render was "authenticated exactly like the browser". It was not. The API reads an access token **only** from the `Authorization` header, and the one cookie (`tl_rt`) is httpOnly and path-scoped to `/api/v1/auth`, so it is never even sent to `/api/v1/me`. A server component holds no access token and cannot mint one — `/auth/refresh` rotates the refresh token, and a server component may not set the replacement cookie. **Every authenticated server render was guaranteed to redirect to login**, including the dashboard that shipped with the scaffold.
      Fixed by splitting rendering along the line that already existed: private pages render on the client through the in-memory-token + refresh middleware (which already handles the cold-start 401); the **public** seller page, the one that must be fast and indexable, stays server-rendered against the public API. Private pages gain nothing from SSR, so this is the correct split rather than a workaround.

- [ ] **P0-12** 🔗 **The public buyer page still 404s. No longer blocked — now a decision.**
      `/public/v1/**` correctly requires an API key. Phase 6 built key issuance, so the blocker is gone, but `/seller/{handle}` still renders not-found (verified 12 Aug) because the web app holds no key.
      _Decide:_ either issue `apps/web` its own first-party server key at boot, or give the buyer page an internal authenticated route instead of going through the partner API. The second is probably right — the buyer page is not a partner, and giving it a partner key means the demo's most visible screen shares a credential path with third parties.
      **This is the screen in the final demo (P2-22). Settle it before that day.**

**Exit criteria:** you can run the whole system offline, with no API keys, and get a Trust Score. ✅ **Met 31 Jul** — except the public buyer page, see P0-12.

---

# Phase 1 — Prove the risky parts (2 days)

**Goal:** find out _now_ whether CNIC OCR and face matching actually work on real Pakistani CNICs. This is the single biggest unknown in the project. Do not postpone it.

### Day 2 — CNIC OCR reality check

- [!] **P1-01** Collect a test set of **10–15 real CNIC images**: good light, poor light, angled, blurry, glare, screenshot-of-a-screenshot. Use your own and volunteers' — with permission. Store outside git.
  **🔴 BLOCKED — needs you. This is a human task and it gates the whole phase.** Full instructions, consent wording and the condition mix are in [`apps/ml/datasets/README.md`](apps/ml/datasets/README.md). Copy `cnic_manifest.example.csv` → `cnic_manifest.csv` and fill in the ground truth.
  _Done when:_ `apps/ml/datasets/cnic/` holds the images and `cnic_manifest.csv` holds the true values.

- [x] **P1-02** Bench harness `apps/ml/bench/ocr_bench.py`.
      _Done 31 Jul:_ reports per-field **and per-condition** accuracy, exact match plus character similarity for names, latency, OCR confidence, manual-review rate, and the gender cross-check rate. Writes JSON for the report. Per-condition matters — an aggregate hides a system that reads clean scans at 95% and night-time phone photos at 20%.

- [ ] **P1-03** Tune `preprocessing.py` (deskew, denoise, contrast, crop) and re-measure.
      _Done when:_ CNIC-number accuracy ≥ 90% on the "good light" subset. **Record the number — it goes in their report.**

- [x] **P1-04** CNIC structural cross-checks — new `trustlens/ai/ocr/cnic_validation.py`.
      _Done 31 Jul:_ 13-digit format, NADRA province code (1–7), repeated-digit placeholders, expiry (incl. lifetime cards), and the gender digit (odd = male, even = female) cross-checked against the printed field. Pure functions with `today` injected, so a decision can be replayed during an appeal. **38 unit tests.**
      Named `is_plausible`, not `is_valid` — passing means nothing contradicts the document, not that it was checked against any register.

- [x] **P1-05** Unreadable CNICs route to manual review instead of failing.
      _Done 31 Jul:_ `FinalizeIdentityVerification` previously returned `FAILED` when OCR produced nothing. `FAILED` applies a **hard cap** in the scoring policy, so a blurry photograph capped a seller's Trust Score with nothing to appeal against. Now resolves to `PENDING` + a review case. Self-contradictory cards route the same way, **ahead of the face-match branch**, so a strong match cannot wave through a card that disagrees with itself. **15 unit tests.**

### Day 3 — Face match reality check

- [!] **P1-06** Build a face-match test set: 10 matching selfie↔CNIC pairs + 10 deliberately mismatched pairs.
  **🔴 BLOCKED — needs you.** Instructions in [`apps/ml/datasets/README.md`](apps/ml/datasets/README.md). Include hard-but-genuine cases (old CNIC photo, beard changed, glasses, headscarf) — that is where honest sellers get wrongly rejected. For the non-matching pairs use same-gender, similar-age people; matching a man's photo against a woman's proves nothing.
  _Done when:_ `face_manifest.csv` has both matching and non-matching rows.

- [x] **P1-07** Bench harness `apps/ml/bench/face_bench.py` with threshold sweep.
      _Done 31 Jul:_ sweeps thresholds 0.30–0.95 and reports **FAR and FRR at each**, not a single accuracy number. Recommends the strictest threshold admitting zero impostors — a false accept is unrecoverable (a scammer verified against a stranger's CNIC now carries a high score), while a false reject only costs an appeal, which the system already supports. Also reports class separation, so you can see whether _any_ threshold cleanly separates them.
      _Still needs:_ real images (P1-06) to produce the numbers.

- [ ] **P1-08** Enable DeepFace anti-spoofing and test it against a printed photo and a phone-screen photo.
      _Done when:_ both spoof attempts are rejected, or the limitation is documented honestly.

- [ ] **P1-09** Record which pretrained weights DeepFace actually downloads, and their licences.
      _Done when:_ a short note exists listing each model and its licence → feeds P7-08 and the report.

- [ ] **P1-10** Confirm model download size and cold-start time; decide baked-into-image vs downloaded-at-boot.
      _Done when:_ `docker/worker.Dockerfile` reflects the decision and the image builds.

**Exit criteria:** you know the real accuracy numbers, and they are written down. If accuracy is poor, you find out in week 1 — not week 8.

---

# Phase 2 — Seller verification UI, mobile-first (8 days)

**Goal:** everything a seller does, end to end, in the browser. The backend exists; this is the missing face of it.

> **Build every screen mobile-first.** Pakistani marketplace users are overwhelmingly on phones, and the buyer score page is the screen shown in the final demo. Retrofitting responsive layouts later costs more than building them this way. Test at 360 px width throughout, not at the end.

### Day 4 — Auth screens

- [x] **P2-01** Registration page with validation, wired to `POST /api/v1/auth/register`.
      _Done 31 Jul._ Uses the shared `registerSchema`. Sends only the five fields the API accepts — `confirmPassword` is a client-side cross-check and the API rejects unknown fields. Registration returns no session (email confirmation is required first), so the form only stores a token if one actually comes back, and otherwise shows a "check your email" state.

- [x] **P2-02** Login flow, session handling and protected-route redirects.
      _Done 31 Jul._ Refactored onto the shared primitives. Honours `?next=` after sign-in, through a `safeNext()` guard that rejects anything not starting with a single `/` — an open redirect on a login page is a phishing gift. Calls `router.refresh()` so the server-rendered dashboard does not paint its logged-out cache first.

- [x] **P2-03** Email verification landing page, forgot-password and reset-password screens.
      _Done 31 Jul._ The verify panel guards against React 19's double-invoked effects with a ref, or the first call spends the token and the second reports "already used". Forgot-password answers identically whether or not the address exists, so it cannot be used to enumerate accounts.

- [x] **P2-03b** Form foundation, shared by every screen in this phase.
      _Done 31 Jul._ `Input`, `Field`, `Alert`, `Spinner`, `Progress` in `@trustlens/ui`, plus a `useApiForm` hook that maps RFC 9457 `errors[]` onto the inputs the user typed into and falls back to a banner only when nothing landed on a field.
      Two mobile rules are baked into `Input` and should not be overridden: `h-11` (44 px touch target), and `text-base sm:text-sm` — Safari on iOS zooms the page whenever a focused input renders below 16 px **and does not zoom back out**, which breaks the layout mid-form.

- [x] **P2-03c** Generate the typed API client.
      _Done 31 Jul._ `pnpm codegen` had never run, so `ApiPaths` was `Record<string, unknown>` and every `api.POST(...)` typed its path as `never`. Wrote the missing `trustlens_api.openapi_export` module (which also fixes `make openapi`, part of P0-09), regenerated `docs/api/openapi.json` from the live API, and generated `schema.gen.ts`. Every route and body is now type-checked against the backend contract.

- [x] **P2-04** **Handle validation** — block reserved and impersonating handles (`olx`, `daraz`, `*-official`). On a trust product, handle squatting is an impersonation vector.
      _Done 11 Aug:_ `domain/policies/handles.py`, 61 tests. Matching is on a canonical form, so
      `d4raz`, `d-a-r-a-z` and Cyrillic lookalikes collapse onto the blocklisted spelling; token-level
      rather than substring, so "Megamart" stays allowed. Reserved names are **refused**, not
      suffixed — `olx-1` trades on the same brand.

  > The confusables table is written as `\uXXXX` escapes on purpose. The first draft used Greek
  > omicron (U+03BF) where it meant Cyrillic o (U+043E), leaving the likelier attack unmapped, and
  > no amount of staring at the source would have shown it — the glyphs are identical.

- [x] **P2-04b** 🚨 **The dashboard was a dead end for every new account.**
      It said "you do not have a seller profile yet" and offered nothing to click.
      `POST /api/v1/me/become-seller` existed and no UI ever called it, so a user could register,
      verify, sign in — and stop. **This was the "nothing works" report:** auth was fine end to end,
      the journey was not. Onboarding form added; verified in a browser through to a working
      checklist at 30/75 points.
      _Note:_ handles are derived server-side from `displayName`; this belongs in the become-seller use case, not the form.

### Days 5-9 — dashboard and the four verification flows

- [x] **P2-05/06** Dashboard shell, navigation, and the verification checklist driven by `GET /api/v1/verification/status`.
      _Done 2 Aug._ Surfaces one obvious next action with its point value rather than four links of equal weight.

- [x] **P2-08/09/10** CNIC upload with consent.
      _Done 2 Aug._ Front, back and selfie upload direct to storage via presigned POST, so a 10 MB photo never touches the API. Explicit biometric consent wired to the backend's existing `ConsentType.BIOMETRIC_PROCESSING` gate. The page states plainly that this is **not** a NADRA check.

- [x] **P2-11/12/13** Selfie capture and job polling.
      _Done 2 Aug._ Polling backs off (1s → 2s → 4s) and stops on a terminal state or after a timeout, so a forgotten tab cannot poll forever. An unreadable upload shows "a reviewer will look at this by hand", matching the P1-05 backend behaviour.

- [x] **P2-14/15/16** Mobile capture, compression and states.
      _Done 2 Aug._ `capture="environment"` for the card and `"user"` for the selfie — phones honour it, desktops ignore it, so one component serves both. Images are re-encoded to a **2000px longest edge**: an OCR-accuracy bound, not a bandwidth one, since the CNIC number is the smallest text on the card. **Do not lower it without re-running `ocr_bench.py`.** Files upload sequentially so per-file progress is honest and three requests do not compete for one mobile connection. Object URLs are revoked on change, or each retake pins another full-size bitmap in memory.

- [x] **P2-17** Phone OTP with resend cooldown.
      _Done 2 Aug._ `autocomplete="one-time-code"` so iOS and Android offer the code from the SMS instead of making people switch apps.

- [x] **P2-18/19** Device fingerprint via **ThumbmarkJS** (MIT — not BSL-licensed FingerprintJS v4).
      _Done 2 Aug._ Headless, lazily imported, never blocking, and silent on failure: the signal only ever _lowers_ a score, so an error a seller cannot act on would be pure harm. **Verified working** — the device check moved `NOT_STARTED` → `VERIFIED` on first dashboard load.
      ⚠️ **Partially done:** only the hash and four coarse attributes are sent, because that is all `DeviceFingerprintRequest` accepts. Storing the component vector — so a browser update that shifts one component does not orphan the device history — needs an API field first.

- [x] **P2-03d** Email resend screen.

### Day 10 — Score & explanation UI

- [ ] **P2-20** Seller trust-score page: gauge, risk band, per-signal breakdown with reasons.
- [ ] **P2-21** "How to improve your score" panel driven by `rank_improvements` — ranked by points recoverable.
- [ ] **P2-22** Polish the public buyer page `(public)/seller/[handle]` — **this is the screen in the final demo**, so it must look finished on both phone and laptop.
      _Done when:_ the buyer page clearly shows score, band, reasons, and verified badges at 360 px and 1440 px.

### Day 11 — Account & data rights

- [ ] **P2-23** Account settings: change password, active sessions, delete account.
- [ ] **P2-24** **Data export and deletion request** flow. _Pakistan's regime gives data subjects access and deletion rights — and it is a strong report section given you hold CNIC and biometric data._
      _Done when:_ a seller can download their data and request deletion.

**Exit criteria:** a seller can go from registration to a published Trust Score entirely through the UI, on a phone.

---

# Phase 3 — Listings module (4 days)

**Goal:** Module 4 of the proposal. The AI analysis job exists; the CRUD and use cases around it do not.

- [x] **P3-01** Listing use cases — create, update, delete, read, list, re-analyse.
      _Done 2 Aug._ Update re-analyses **only when the title or description changed**; those are what the analyser reads, so re-running an LLM call for a corrected city name is money spent on an identical verdict. Delete is **soft** — a hard delete would let a seller erase the evidence behind a published Trust Score, making any appeal against it unanswerable. A missing listing and someone else's listing return the same error, so the endpoint cannot enumerate ids.

- [x] **P3-02** `routers/listings.py` — full CRUD plus `POST /{id}/analyse`.
      _Verified 2 Aug:_ 38 endpoints live; create returns `ANALYSING` with a queued job, list paginates.
      _Fixed on the way:_ `PageMeta` was being constructed directly instead of via `build()`, leaving `total_pages`/`has_next`/`has_prev` unset and 500-ing the list endpoint.

- [x] **P3-07** **Prompt-injection containment** — 12 tests.
      _Done 2 Aug._ Pins the **blast radius**, not the model. Injection strings are stored as ordinary text (blocklisting phrasings is theatre, and would reject honest listings that quote one) while length caps bound what can reach a prompt. The load-bearing test drives the scoring policy with **both listing signals passing**, as though the injection fully succeeded, and asserts the seller still cannot reach LOW risk — a captured analyser is worth 30 of 100 points and no verification status.

- [x] **P3-03** LLM verdict persisted end to end.
      _Verified 3 Aug._ A scam-pattern listing went `ANALYSING` → **FLAGGED**, risk 74, labels `urgency_pressure` + `advance_fee`, and `LISTING_CONTENT_SAFE` moved to FAIL 0/10.
- [x] **P3-04** Price-outlier detection — **and two defects fixed that made it award points on no evidence.**
      _Done 3 Aug._ The plumbing existed, but live data showed it was silently broken:
      **1. No minimum sample size.** With one listing in a category the median _is_ that listing, so its deviation is 0% and the signal reported "prices are in line with similar items" — a PASS the seller never earned. `category_median_price` now returns None below `MIN_COMPARABLE_LISTINGS` (5), so the signal is UNAVAILABLE and excluded from the denominator. **Verified:** the signal moved from `PASS 5.0/5.0` to `UNAVAILABLE 0.0/0.0`.
      **2. Free-text categories fragmented the corpus.** The dev database held `Mobile Phones`, `mobile-phones` and `mobiles` as three buckets for one category, so a phone was never compared against other phones. Categories are now a controlled vocabulary shared by the constants package, the zod schema, the domain and the form dropdown, with normalisation for case and separator variants. 23 tests.
- [ ] **P3-05** `imagehash` duplicate-photo detection. _(`ListingImage.perceptual_hash` column already exists.)_
- [x] **P3-06** Seller listings UI — list, create, edit, remove, per-listing risk panel.
      _Done 3 Aug._ The risk panel translates analyser codes into plain English ("Pressures the buyer to decide immediately"), and reports only _underpricing_ — an overpriced listing is a bad deal, not a scam, and flagging it would train sellers to ignore the panel. Removal is soft and says why: the evidence behind an already-published score has to survive so it can still be appealed.
      _Not done:_ listing **image upload** — deferred with P3-05, since both need the same image pipeline.

**Exit criteria:** a seller posts a listing, AI analyses it, and both listing signals move the Trust Score.

---

# Phase 4 — Admin panel (5 days)

**Goal:** Module 7. Currently placeholder headings and an empty use-case folder.

- [x] **P4-01** `use_cases/admin/` review queue — list, claim, decide, with audit logging.
      _Done 3-4 Aug._ Claiming is what stops two reviewers deciding the same case differently, so a case assigned to someone else is refused. The audit entry is written in the **same transaction** as the decision — one written afterwards can be lost exactly when it matters. Deciding never writes a score; it records a verdict and enqueues a recompute (ADR-0002).

- [x] **P4-02** `routers/admin.py` — queue, claim, decide, permission-gated per route.
      _Verified 4 Aug._ seller 403 · reviewer 200 · admin 200 · anonymous 401. A two-word decision note is rejected 422. A full claim→decide cycle wrote two audit rows carrying actor, before/after and reason.

- [x] **P4-00** 🚨 **Admin and reviewer accounts could not sign in at all.**
      _Found and fixed 4 Aug._ Login returned `MFA_REQUIRED` for both roles and **no MFA enrolment or verification endpoint exists anywhere in the API**, so the requirement could never be satisfied. `SECURITY_MFA_REQUIRED_ROLES` looked like the control for this but was **dead config** — `User.requires_mfa` hardcoded `{ADMIN, REVIEWER}`, so nothing could reach the decision. The entire admin panel and appeal queue were unreachable.
      Fixed by making the policy take the required roles (defaulting to the hardcoded pair, so production is unchanged) and having the login route pass the configured value. Development clears it; `.env.example` keeps the strict default with a warning.
      ⚠️ **Still open:** MFA is unimplemented. Either build it or document the omission before production — do not simply ship the setting empty.

- [ ] **P4-01b** Remaining admin use cases: seller search

- [ ] ~~**P4-01** Implement `use_cases/admin/`~~ — seller search, review queue, decision recording, audit log. _(currently empty)_
- [ ] **P4-02** Add `routers/admin.py` with RBAC enforced (admin/reviewer roles only).
- [x] **P4-03** Admin dashboard — live queue counts (waiting / claimed / decided).
      _Done 4 Aug._ Counts by risk band still need a seller-search endpoint (P4-01b).

- [x] **P4-06b** 🚨 **The admin app had no authentication at all**, and `adminFetch` forwarded cookies that are path-scoped to `/auth` — it could never have worked. Deleted and replaced with the same client-side session the seller app uses. Login sits outside the `(dashboard)` group, since guarding it would redirect the login page to itself.

- [x] **P4-06c** 🚨 **Session-cache bug, in _both_ apps.** The guard asks "who is this?" before redirecting to login and caches the answer: nobody. Signing in put a token in memory but left that cached `null` in place, so the guard read it and bounced straight back — with a `200 OK` login sitting in the network tab. Both logins now drop the cached session before redirecting.

- [ ] **P4-03b** Counts by risk band, pending reviews, recent flags _(needs P4-01b)_.
- [ ] **P4-04** Seller list: search, filter by risk band and flag status, pagination.
- [ ] **P4-05** Seller detail: full signal breakdown, verification history, score history, evidence viewer.
- [ ] **P4-06** Manual identity review screen — CNIC and selfie via **short-lived signed URLs only**, approve/reject with reason.
- [ ] **P4-07** Scoring-model admin: view weights, adjust, publish a new version. _(Weights are versioned in the DB — old scores must keep referencing the version that produced them.)_
- [ ] **P4-08** Audit trail: every admin action recorded with actor, timestamp, before/after.
      _Done when:_ an admin can find a seller, review their CNIC, override a decision, and the action is logged.

---

# Phase 5 — Appeals (3 days)

**Goal:** the appeal loop promised in the proposal. Entity and tables exist; all logic is missing.

- [x] **P5-01** `use_cases/appeals/` — submit, withdraw, claim, message, resolve, rescore. 31 tests.
- [x] **P5-02** `routers/appeals.py` — 8 endpoints, seller and reviewer routes gated separately.
- [x] **P5-03** Seller UI on the score page, under the breakdown: category + reason, thread, withdraw.
- [x] **P5-04** Admin UI: queue, claim, decision with mandatory note, internal notes, override guard.
- [x] **P5-05** `notifications.send_email` enqueued on every resolution.
      _Verified 11 Aug:_ e2e spec `testing/e2e/specs/appeals.spec.ts` drives both apps in one run —
      seller disputes a score, reviewer claims and resolves, appeal leaves the queue. The worker
      recomputes with `trigger='APPEAL_RESOLUTION'`.

**Properties held, and checked by test rather than by hope:**

- An appeal names **one computation**, not "my score" — required exposing the score id on the
  trust-score response, which it did not have, so appealing was literally impossible from the UI.
- Resolving **never writes a score**. `RECOMPUTE` corrects the evidence and re-runs the engine;
  `OVERRIDE` is admin-only, needs a reason and expires; `REJECT` closes with an explanation.
- A reviewer attempting an override gets **403** from both the router and the use case.
- Internal reviewer notes are stripped before the seller ever sees the thread.
- A seller cannot read, act on, or post to another seller's appeal — **404, not 403**, so the id
  is not an enumeration oracle.

- [x] **P5-06** 🚨 **Two rescore jobs had never run — one of them since Phase 4 shipped.**
      `trigger="APPEAL"` and `trigger="MANUAL_REVIEW"` are not `ScoreTrigger` members. The job
      raised `ValueError` **after** the endpoint had already returned `200`, so every admin review
      decision recorded its verdict, wrote its audit entry, notified nobody of a problem — and
      never rescored the seller. Found by reading the worker log rather than the response.
      A test now scans the source for `trigger=` literals and parses each one, so the next
      plausible-looking name fails in CI instead of in production.

- [x] **P5-07** The reviewer queue listed resolved and withdrawn appeals alongside open work.
      Claiming one fails, and a queue whose top row cannot be actioned reads as a broken screen.

- [x] **P5-08** The appeal form re-reads the current score id immediately before submitting.
      A page left open while a verification finishes held a superseded id and earned "your score
      has been recomputed since this one" — true, and unactionable, since the seller is objecting
      to the same verdict either way. One extra `GET` turns a dead end into a submission.

---

# Phase 6 — Public marketplace API (3 days)

**Goal:** Module 8. The score endpoint exists; key management around it does not.

- [x] **P6-01** `use_cases/public_api/` — key issue, rotate, revoke, usage accounting.
      _Done 12 Aug._ The plaintext key exists once, in the issue response, and only an argon2 hash is stored — a design where support can read a key back is a design where a database dump is a set of live credentials. **Rotation is not revocation:** rotating issues a replacement and _expires_ the old key after a 24-hour overlap, because revoke-then-issue takes the partner down for the length of their deploy, which is why in practice nobody rotates and leaked keys stay live for months. Revocation has no overlap. A key cannot be issued for a partner who is not ACTIVE. 21 tests.

- [x] **P6-02** Partner registration + key management screens.
      _Done 12 Aug._ Register, approve, suspend, issue, rotate, revoke, with usage against quota per partner. Revoke is two clicks (immediate, no overlap — a misclick takes a live partner offline); rotate is one, because friction there just means nobody rotates. The plaintext is held in component state and never written to a query cache.

- [x] **P6-03** Per-key rate limiting and quota enforcement via Redis.
      _Already built in the scaffold_ — the tracker was wrong. Verified: per-minute limit by tier, monthly quota, and it fails **closed** when Redis is unavailable, since for a partner-facing endpoint refusing traffic beats silently removing the only control on cost and abuse.

- [x] **P6-04** **HMAC-signed responses** so a marketplace can prove a score is authentic.
      _Done 12 Aug._ `X-TrustLens-Signature: t=<ts>,v1=<hmac>` over the **exact bytes served** — the response is built in the handler rather than left to FastAPI, because signing one encoding and sending another fails verification for reasons nobody can reproduce. The timestamp is inside the signed material, so a captured "score: 95" cannot be replayed forever. Verified independently: a tampered body fails the check. 12 tests.

- [x] **P6-05** Webhook delivery on score change, with retries and signature.
      _Done 12 Aug._ Fan-out happens in the outbox relay, so delivery rows are written in the **same transaction** as the event being marked published — "the score changed but nobody was told" cannot happen. Retries back off 30s/1m/2m/4m and then stop; only failures retrying can fix are retried (a 400 will be exactly as wrong in four minutes). Verified against a real receiver that returned 500 once: the retry arrived and was accepted, and the partner's independent HMAC check passed.
      _Two defects found by running it rather than reading it:_ the fan-out compared domain event names (`trust_score.computed`) against the webhook enum (`SCORE_UPDATED`) and would have matched **nothing**; and `events.contains()` raises `NotImplementedError` on the generic ARRAY type.

- [x] **P6-06** Public API documentation page + Postman collection (`make postman`).
      _Done 12 Aug._ Written for the engineer handed a key and an afternoon, with real captured responses rather than idealised ones — including the parts that look like bugs on day two: `unavailableSignals` are checks that could not run and are excluded rather than counted against the seller, and a 404 means "no record", not "fraudulent". Carries a copy-pasteable signature verifier.

**Exit criteria met:** an external `curl` with a valid key returns a signed score whose signature verifies; an invalid key is rejected 401, a revoked one 410, and both rate limit and quota return 429.

---

# Phase 7 — ML scam classifier (4 days)

**Goal:** the trained model that makes this a genuine _AI_ FYP rather than an API wrapper. **This is the marks-winning phase.**

> `apps/ml` is referenced by `scam_classifier.py` (_"Train it with `make -C apps/ml train`"_) but was never created.

- [ ] **P7-01** Create the `apps/ml` package: data, training, evaluation, export.
- [ ] **P7-02** Acquire and prepare datasets — the fake-job-postings set (~18k rows) and the DIFrauD deceptive-text corpus as proxies, plus a small hand-labelled set of Pakistani marketplace ads.
- [ ] **P7-03** Train a **TF-IDF + Logistic Regression baseline** first. _You need a baseline to compare against, or the deep model's numbers mean nothing._
- [ ] **P7-04** Fine-tune **DistilBERT** on free Google Colab GPU. Export to ONNX for cheap CPU inference.
- [ ] **P7-05** Evaluation: accuracy, precision, recall, F1, ROC-AUC, confusion matrix — baseline vs. DistilBERT. **Save the plots; they go straight into the report.**
- [ ] **P7-06** Wire the exported model into `scam_classifier.py` behind the existing port so `USE_FAKE_AI=false` uses it.
- [ ] **P7-07** Write `apps/ml/README.md` — dataset, method, results, limitations.
- [ ] **P7-08** **Model licence note** — record that the pretrained face weights are non-commercial research licences, which academic FYP use permits. Feeds the report's limitations section.
      _Done when:_ `make -C apps/ml train` works end to end and produces a metrics report.

**Exit criteria:** Haseeb and Muttayab can stand in the viva and say _"we trained this, here is our confusion matrix."_

---

# Phase 8 — Real integrations (4 days)

**Goal:** flip off the fakes, one provider at a time.

- [ ] **P8-01** Email via Resend (3,000/month free) — verification and notification templates.
- [ ] **P8-02** **Email deliverability: SPF, DKIM, DMARC on the sending domain.** _If verification emails land in spam, signup silently breaks and you will never see an error. Test against Gmail, Outlook and Yahoo._
- [ ] **P8-03** SMS OTP via Twilio trial — **demo-scale only**, mock driver stays the development default. Document the PTA/carrier registration constraint as a deployment limitation.
- [ ] **P8-04** IP/VPN detection via proxycheck.io or vpnapi.io free tier, with cache and a **fail-open** path.
- [ ] **P8-05** Disposable-email detection using a local domain list (no API needed).
- [ ] **P8-06** Object storage: MinIO locally, Cloudflare R2 in production, signed URLs both ways.
- [ ] **P8-07** Verify the existing `purge_expired_media` cron actually deletes CNIC and selfie images after the decision + appeal window. _(The cron exists — confirm it works end to end.)_
- [ ] **P8-08** Verify every provider degrades gracefully. A provider outage must produce `UNAVAILABLE`, never a `FAIL` a seller cannot appeal.
      _Done when:_ the system runs correctly with `USE_FAKE_AI=false`, and still runs with every external key removed.

---

# Phase 9 — Deployment (3 days)

- [ ] **P9-01** Provision Postgres (Neon), Redis (Upstash), storage (R2).
- [ ] **P9-02** Deploy `apps/web` and `apps/admin` to Vercel with production env vars.
- [ ] **P9-03** Deploy `apps/api` + `apps/worker`. **Decide VPS vs Railway** — the worker image is ~2.5 GB because of torch/DeepFace, which is tight on Railway's small containers.
- [ ] **P9-04** Run migrations against production; seed reference data only (never demo data).
- [ ] **P9-05** Custom domain, HTTPS, CORS, production secrets via `scripts/generate-keys.sh`.
- [ ] **P9-06** Confirm CI (`.github/workflows/ci.yml`) is green and deploys on merge to `main`.
- [ ] **P9-09** ⚠️ **The worker dies permanently when Redis drops the connection.**
      _Found 3 Aug._ Both worker processes exited with `redis.exceptions.ConnectionError: Connection closed by server` when the dev containers stopped, and neither came back. The cause was environmental — Docker Desktop shut down overnight — but the **behaviour** is the problem: one Redis blip means no OCR, no face matching, no emails, no OTP and no rescoring until a human notices, and nothing announces it.
      This matters more in production than locally: **Upstash closes idle connections**, so this will happen without anyone stopping anything.
      _Needs:_ a reconnect/retry loop around the ARQ worker, a process restart policy (`restart: unless-stopped` in compose, or the platform equivalent), and an alert when the worker is not consuming — pairs with P9-07.
      _Done when:_ stopping and restarting Redis leaves the worker consuming jobs again without manual intervention.

- [ ] **P9-07** **Basic monitoring** — fill the empty `shared/telemetry/`: structured error logging (Sentry free tier), uptime check, and an alert to your email when the API is down.
- [ ] **P9-08** **Backups with a tested restore.** Take a backup, restore it into a scratch database, confirm it works. _An untested backup is not a backup._
      _Done when:_ the full seller journey works on the public URL, not just localhost.

---

# Phase 10 — QA & demo readiness (4 days)

- [ ] **P10-01** Raise domain test coverage; add integration tests for each use case.
- [ ] **P10-02** Playwright E2E: full seller journey, buyer lookup, admin review, appeal.
- [ ] **P10-03** Security pass — OWASP basics, auth rate limiting/brute-force protection, RBAC checks, PII leak scan on API responses.
- [ ] **P10-04** Load-test the public score endpoint; confirm the "score within seconds" claim with real p95 numbers.
- [ ] **P10-05** Cross-browser and cross-device check: Chrome, Safari on iPhone, Chrome on Android.
- [ ] **P10-06** **Fix the stale docs.** `ARCHITECTURE.md` §6 still says _"No implementation code has been written yet"_; `docs/05` says 30 tables but the migration creates 40; `ARCHITECTURE.md` §4 lists `infrastructure/`, `tools/` and `apps/ml`, none of which exist.
- [ ] **P10-07** Seed a convincing demo dataset — sellers across all three risk bands, including a clear scammer profile and a clear genuine profile.
- [ ] **P10-08** Write and time the demo script. Rehearse it end to end.
- [ ] **P10-09** **Demo fallback plan** — recorded video and screenshots, in case the venue's internet fails on the day.
      _Done when:_ the demo runs start to finish without a single manual database fix.

---

# Phase 11 — Handover & training (3 days)

**Goal:** the students can run, explain and defend the system after you step away. Without this phase, "delivery" turns into unpaid support forever.

- [ ] **P11-01** Transfer credentials and ownership: GitHub, Vercel, Railway/VPS, Neon, Upstash, R2, Twilio, Resend. Documented in one place.
- [ ] **P11-02** Write `RUNBOOK.md` — how to start it, deploy it, roll back, read logs, reset a password, and what to do when a job queue backs up.
- [ ] **P11-03** **Architecture walkthrough session** with Haseeb and Muttayab: why ports/adapters, why deterministic scoring, why the worker is separate, how the score is computed. _They present this, not you._
- [ ] **P11-04** Admin panel training: how to review an identity, resolve an appeal, publish a scoring-model version.
- [ ] **P11-05** **Viva preparation** — rehearse the three hard questions until their answers are fluent:
  1. _"How is this different from OLX, which also does OTP?"_ → OTP verifies a SIM, not a person; OLX's incentive is more signups, not more friction; the score is portable across marketplaces; and no marketplace explains **why**.
  2. _"Can you actually verify a CNIC is real?"_ → No. Document plausibility + face match only. **Never claim NADRA verification.**
  3. _"Where is the AI you built yourself?"_ → Phase 7, with the confusion matrix.
- [ ] **P11-06** Agree the **support window** in writing — what you will fix, for how long, and what counts as new work.
      _Done when:_ a student can deploy a change and resolve an appeal without asking you.

---

# Track D — FYP academic deliverables (9 days, parallel)

**This is what they are graded on.** The software is the evidence; these documents are the submission.

> ⚠️ **Ownership is undecided.** Agree now whether you write these or the students do. If it lands on you unplanned, it is roughly two weeks of unbilled work.

- [ ] **D-01** Update the **SRS** to match what was actually built — especially the scope correction: TrustLens scores **enrolled** sellers, and returns "no record" for everyone else.
- [ ] **D-02** Correct the "within seconds" claim: score _reads_ are sub-second; _enrollment verification_ takes 30–60 seconds. State both.
- [ ] **D-03** Design documents: use-case diagrams, DFDs (levels 0–2), sequence diagrams for the verification and scoring flows.
- [ ] **D-04** **ER diagram** for all 40 tables (`make erd` once P0-09 fixes it).
- [ ] **D-05** Test documentation: test cases, results, coverage summary, the Phase 1 accuracy numbers, and the Phase 7 model metrics.
- [ ] **D-06** Final report chapters: introduction, literature review, methodology, implementation, results, conclusion.
- [ ] **D-07** **Limitations chapter** — no NADRA verification, device fingerprinting is 60–80% accurate, VPN ≠ fraud, non-commercial model licences, SMS constrained by PTA registration. _Stating limits honestly reads as maturity, not weakness._
- [ ] **D-08** **Future Scope chapter** — reverse-image stolen-photo detection, chat scam detection, buyer scam-report feedback loop, marketplace integrations, reputation history, mobile app.
- [ ] **D-09** Final presentation deck and demo video.

---

## Known risks

| Risk                                                 | Impact | Mitigation                                      |
| ---------------------------------------------------- | ------ | ----------------------------------------------- |
| OCR/face accuracy poor on real CNICs                 | High   | Phase 1 measures it in week 1, not week 8       |
| Architecture too complex for students to defend      | High   | P11-03 and P11-05 — budget real teaching time   |
| Track D silently lands on you unpaid                 | High   | Decide ownership **before** Phase 2 starts      |
| Worker image (~2.5 GB) too big for Railway free tier | Medium | P9-03 — VPS is the safer choice                 |
| Two people pushing to `main` and colliding           | Medium | Agree module ownership before Phase 2           |
| `apps/ml` never gets built, leaving no trained model | Medium | Phase 7 is not optional — it is the AI claim    |
| Verification emails land in spam                     | Medium | P8-02 — SPF/DKIM/DMARC, tested across providers |
| Demo fails on the day (no internet, cold start)      | Medium | P10-09 — recorded fallback                      |

---

## Decisions still open

1. **Final submission date** — needed to map 53 days onto real dates.
2. **Track D ownership** — you or the students. Biggest unpriced risk in this plan.
3. **VPS or Railway** for backend + worker.
4. **Module ownership split** between you and Faisal bhai.

---

_Last updated: 31 July 2026 · Scope: academic FYP_
