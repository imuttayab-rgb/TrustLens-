# TrustLens — What's left, in order

**Companion to [`TASKS.md`](TASKS.md).** That file is the full history of the project,
including everything already finished. This file is the short version: only what is
**not done**, arranged in the order it should be done.

Task IDs are the same in both files. Tick a box here, tick it in `TASKS.md` too.

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked on someone else

---

## Where we are

|                         |                                     |
| ----------------------- | ----------------------------------- |
| Software track          | ~24 of 44 days done — **about 55%** |
| Documentation track (D) | 0 of 9 days done — **0%**           |
| **Whole FYP**           | **about 46%**                       |
| Phases finished         | 0, 5, 6 — most of 2, 3 and 7        |
| Phases untouched        | 10, 11, and Track D                 |

The hard part is behind us. Architecture, auth, verification, scoring, appeals and the
partner API are built and working. What remains is more items but less risk.

---

## Stage 0 — Corrections first ✅ done 22 Aug

- [x] **P0-12** Fix the public buyer page 404.
      **Decided: a first-party route, not a partner key.** New
      `GET /api/v1/public/sellers/{seller_ref}/trust-score` — anonymous, IP rate limited, and
      reusing the _same_ use case and response model as the partner API, so the PII-free
      guarantee is inherited rather than re-implemented. Giving `apps/web` a partner key was
      rejected: a revoked key or an exhausted quota would then take the demo's opening screen
      down with it. Verified live: the page returns **200** with a real score where it
      returned 404, and an unknown handle still 404s.

- [x] **P0-16** 🚨 **The startup route guard had been checking almost nothing.** Found while
      relying on it for P0-12. FastAPI 0.141 defers `include_router`, so the guard walked 8
      placeholders and saw **1 route out of 59** — and only warned where its docstring
      promised a failed boot. Now walks the real tree and raises. The codebase was clean
      (0 unguarded); the check was blind.

- [x] **P0-17** 🚨 **Every reason on the buyer page was labelled "Identity."** The page
      hardcoded the category, so "The email address was confirmed" was shown to buyers as an
      identity check. Invisible until P0-12, because the page never rendered a reason. The
      public payload now carries the signal category.

- [x] **P0-18** **Three e2e tests could never have passed.** `public-score.spec.ts` asserted
      the page shows a score — against a page that always 404'd — and two more had drifted
      into Playwright strict-mode violations. All fixed; the suite is **7/7 green**.

- [x] **P10-06** Fix the stale documentation. `README.md` ("Design phase … implementation has
      not started") and `ARCHITECTURE.md` ("No implementation code has been written yet") now
      carry measured status. Table count 30 → 40. The fictional `infrastructure/` path was
      also in **runnable commands** in `docs/11` and `docs/16`, which would have failed for
      anyone who copied them.

- [x] **P0-19** 🚨 **CI's Prettier gate had never passed.** 50-odd committed Markdown files
      were never formatted (the pre-commit hook only reaches _staged_ files), and
      `.import_linter_cache/` was missing from the root `.gitignore` while its three sibling
      caches were listed — so the gate also failed on any machine that had run
      `make check-arch`. Both fixed; `pnpm format:check` is clean.

- [x] **P0-15** Correct the stale boxes in `TASKS.md` — **P2-20**/**P2-21** were done on
      11 Aug and never ticked; the duplicate **P4-01**/**P4-02** entries were superseded.

---

## Stage 1 — Unblock the accuracy numbers (students, starts today)

**This has been stuck since week 1 and it is the only thing Zohaib cannot do alone.**
Without it there are no accuracy figures, and without those there is no results chapter.
Start it now and let it run in the background of everything else.

- [!] **P1-01** Collect **10–15 real CNIC images** — good light, poor light, angled, blurry,
  glare, screenshot-of-a-screenshot. Own and volunteers', with permission. Stored
  outside git. Instructions and consent wording: `apps/ml/datasets/README.md`.
  _Done when:_ `apps/ml/datasets/cnic/` holds the images and `cnic_manifest.csv` holds
  the true values.

- [!] **P1-06** Build the face-match set — 10 matching selfie↔CNIC pairs, 10 deliberately
  mismatched. Include hard-but-genuine cases (old photo, beard, glasses, headscarf).
  Non-matching pairs must be same gender and similar age.
  _Done when:_ `face_manifest.csv` has both matching and non-matching rows.

**Then, once the images exist (Zohaib, ~1.5 days):**

- [ ] **P1-03** Tune `preprocessing.py` (deskew, denoise, contrast, crop) and re-measure.
      _Done when:_ CNIC-number accuracy ≥ 90% on the good-light subset. **Write the number down.**
- [ ] **P1-11** Benchmark **both** engine pairs — easyocr/DeepFace vs RapidOCR/InsightFace —
      on the same images, and choose on measured accuracy. Both are already in the tree
      behind `OCR_ENGINE` / `FACE_ENGINE`.
      _Done when:_ a comparison table exists. "We compared two approaches and chose on
      measured accuracy" is a far better methodology chapter than "we picked one".
- [ ] **P1-08** Enable anti-spoofing; test against a printed photo and a phone-screen photo.
      _Done when:_ both spoofs are rejected, or the limitation is documented honestly.
- [ ] **P1-09** Record which pretrained weights are downloaded and their licences → feeds P7-08.
- [ ] **P1-10** Confirm model download size and cold-start time. _(Largely answered by the
      Step 4 measurements in `docs/20-go-live-plan.md` — write the conclusion down.)_

---

## Stage 2 — The scam classifier ✅ built 22 Aug · 🔴 blocked on data

> **The model works and it does not work, and both matter.**
>
> | Measured on                                | Precision | Recall                  | F1        |
> | ------------------------------------------ | --------- | ----------------------- | --------- |
> | Held-out split of its own training corpora | 0.918     | 0.894                   | **0.906** |
> | A fraud corpus it never trained on         | 0.698     | 0.665                   | **0.681** |
> | A different one, same test                 | 0.320     | 0.714                   | **0.442** |
> | Pakistani marketplace ads                  | —         | **1 of 7 scams caught** | —         |
>
> Shown _"Send advance payment via easypaisa. WhatsApp me, no calls. Today only,
> hurry!"_ it says **genuine, p = 0.13**. The 30-line keyword placeholder catches
> 4 of those 7. The training data is English **job adverts**; the product scores
> Pakistani **marketplace ads**. The fix is data, not a bigger model.

- [x] **P7-01** `apps/ml` training package — CLI, Makefile, workspace member, and an
      import-linter contract (6 now) so training code can never reach production.
- [~] **P7-02** Datasets. **Proxies done** — EMSCAD (CC0) and DIFrauD (MIT), 36,695 rows.
  🔴 **300–500 hand-labelled Pakistani ads still needed.** Template and labelling
  instructions in `apps/ml/README.md`. Human task; gates the phase.
- [x] **P7-03** TF-IDF + Logistic Regression baseline — trained, exported, reproducible.
- [~] **P7-04** DistilBERT — script written and split-matched, **not run** (needs a Colab
  GPU). Its header says capacity is not the bottleneck; P7-02 buys more.
- [x] **P7-05** Evaluation — P/R/F1/ROC-AUC/PR-AUC, plots, accuracy always shown against
      the majority-class baseline, plus a **cross-corpus test** the plan did not ask for.
      That test is what turned a 0.906 success story into the table above.
- [x] **P7-06** Wired behind the existing port; `USE_FAKE_AI=false` loads the artifact.
- [x] **P7-07** `apps/ml/README.md`.
- [x] **P7-08** Licence note — the classifier is unencumbered (CC0/MIT/BSD/Apache); the
      **face** weights are the non-commercial ones, which academic FYP use permits.
- [x] **P7-09** 🚨 Figures and tables were drawn from different rows (the CLI re-split
      after training had deduplicated). Fixed; the evaluated split now travels with the
      result.

**⚠️ Do not enable this as a live scoring input yet.** `jobs/listings.py` combines it as
`max(llm_risk, classifier × 100)`, so a false positive _becomes_ the listing's risk and
flows into a seller's trust score. Turning it on is gated on P7-02.

**What is left in this stage:** collect the local ads (P7-02), re-run
`make -C apps/ml train`, and — if a GPU is free — run the DistilBERT script (P7-04).

---

## Stage 3 — Get it on the internet (Phase 9 + accounts, 3 days, Zohaib)

Steps 1–4 of `docs/20-go-live-plan.md` are done (Redis resilience, contract tests, ONNX
adapters, slimmed image). Steps 5–6 are not. Nothing is deployed anywhere.

**Provision:**

- [ ] **P9-01** Postgres (Neon), Redis (Upstash), storage (Cloudflare R2). All free tier.
- [ ] **P8-01** Email via Resend (3,000/month free) — verification and notification templates.
      _(The `ResendEmailSender` adapter is already written. This is an account, not code.)_
- [ ] **P8-02** **SPF, DKIM, DMARC on the sending domain.** Test against Gmail, Outlook and
      Yahoo. If verification emails land in spam, signup silently breaks and nothing errors.
- [ ] **P8-06** Object storage: MinIO locally, R2 in production, signed URLs both ways.

**Deploy:**

- [ ] **P9-02** `apps/web` and `apps/admin` to Vercel with production env vars.
- [ ] **P9-03** `apps/api` + `apps/worker` to Fly.io. ⚠️ **Decided by measurement:** the worker
      peaks at **323 MB RAM**, so it needs a 512 MB instance — roughly **$3–4/month**, not
      $0. Everything else fits a free tier.
- [ ] **P9-04** Run migrations against production; seed **reference data only**, never demo data.
- [ ] **P9-05** Custom domain, HTTPS, CORS, production secrets via `scripts/generate-keys.sh`.
- [ ] **P9-06** Confirm CI is green and deploys on merge to `main`.

**Prove it, then watch it:**

- [ ] **P9-10** _(Step 6)_ Run the whole journey against the **public URLs**: register → verify
      email → become seller → upload CNIC → score computed by the **real** engine → public
      page renders → partner key reads a signed score → webhook fires.
      _Done when:_ that sequence completes on the deployed system, not on localhost.
- [ ] **P9-07** **Monitoring.** `shared/telemetry/__init__.py` is a **0-byte file** — there is
      no error logging, no uptime check, no alerting. Sentry free tier + an uptime ping +
      an email alert when the API is down.
- [ ] **P9-08** **A backup with a tested restore.** Take one, restore it into a scratch
      database, confirm it works. An untested backup is not a backup.

**Remaining providers (code exists, needs switching on and proving):**

- [ ] **P8-03** SMS OTP via Twilio trial — demo scale only. Document the PTA/carrier
      registration constraint as a deployment limitation, not a defect.
- [ ] **P8-04** IP/VPN detection via proxycheck.io or vpnapi.io free tier, with cache and a
      **fail-open** path.
- [ ] **P8-05** Disposable-email detection from a local domain list. _(A fallback list already
      exists in `signal_collector.py` — replace it with the full list.)_
- [ ] **P8-07** Verify the `purge_expired_media` cron **actually deletes** CNIC and selfie
      images after the decision + appeal window. The cron is registered; confirm end to end.
- [ ] **P8-08** Verify every provider degrades gracefully. A provider outage must produce
      `UNAVAILABLE`, never a `FAIL` a seller cannot appeal.

---

## Stage 4 — Finish the admin panel (Phase 4 remainder, 3 days, Zohaib)

The reviewer queue works end to end. Everything else in the admin app is a placeholder —
`sellers/page.tsx` is 12 lines of heading, `scoring/page.tsx` is read-only, and
`routers/admin.py` exposes only three endpoints (queue, claim, decide).

_This stage can run in parallel with Stage 3 if someone else is handling deployment._

- [ ] **P4-01b** Seller-search use case + endpoint. Everything below depends on it.
- [ ] **P4-04** Seller list: search, filter by risk band and flag status, pagination.
- [ ] **P4-05** Seller detail: full signal breakdown, verification history, score history,
      evidence viewer.
- [ ] **P4-06** Manual identity review screen — CNIC and selfie via **short-lived signed URLs
      only**, approve/reject with a reason.
- [ ] **P4-03b** Dashboard counts by risk band, pending reviews, recent flags.
- [ ] **P4-07** Scoring-model admin: view weights, adjust, publish a new version. Weights are
      versioned in the DB — **old scores must keep referencing the version that produced them.**
- [ ] **P4-08** Audit trail: every admin action recorded with actor, timestamp, before/after.
- [ ] **P4-09** **MFA decision.** The staff-login MFA setting exists but MFA is unimplemented.
      Either build it or document the omission — do not ship the setting empty.

_Stage done when:_ an admin can find a seller, review their CNIC, override a decision, and
the action is logged.

---

## Stage 5 — Seller-side leftovers (2.5 days, Zohaib)

- [ ] **P2-22** Polish the public buyer page. _(Needs P0-12 first.)_
      _Done when:_ it clearly shows score, band, reasons and verified badges at **360 px and
      1440 px**. This is the screen in the final demo — it must look finished on a phone.
- [ ] **P3-05** Listing **image upload**, plus `imagehash` duplicate-photo detection. The
      `ListingImage.perceptual_hash` column and index already exist but nothing writes them,
      and `ListingForm` has no image field at all. Both need the same pipeline.
- [ ] **P2-23** Account settings: change password, active sessions, delete account.
- [ ] **P2-24** **Data export and deletion request** flow. Pakistan's regime gives data
      subjects access and deletion rights — and it is a strong report section given the
      system holds CNIC and biometric data.
      _Done when:_ a seller can download their data and request deletion.

---

## Stage 6 — QA and demo readiness (Phase 10, 4 days, Zohaib)

Currently three Playwright specs, 169 lines total — auth, appeals, public score only.

- [ ] **P10-01** Raise domain test coverage; integration tests for each use case.
- [ ] **P10-02** Playwright E2E: full seller journey, buyer lookup, admin review, appeal.
- [ ] **P10-03** Security pass — OWASP basics, auth rate limiting and brute-force protection,
      RBAC checks, PII leak scan on API responses.
- [ ] **P10-04** Load-test the public score endpoint. **Confirm the "score within seconds"
      claim with real p95 numbers** — or correct the claim (see D-02).
- [ ] **P10-05** Cross-browser and cross-device: Chrome, Safari on iPhone, Chrome on Android.
- [ ] **P10-07** Seed a convincing demo dataset — sellers across all three risk bands,
      including one clear scammer and one clear genuine profile.
- [ ] **P10-08** Write and **time** the demo script. Rehearse it end to end.
- [ ] **P10-09** **Demo fallback plan** — recorded video and screenshots, for when the venue's
      internet fails on the day. ⚠️ Neon sleeps after 5 minutes idle; ping it before the demo
      so the examiner's first click is not the wake-up call.

---

## Stage 7 — Handover and training (Phase 11, 3 days, Zohaib + students)

- [ ] **P11-01** Transfer credentials and ownership — GitHub, Vercel, Fly, Neon, Upstash, R2,
      Twilio, Resend — documented in one place. _(`CREDENTIALS.dev.md` is a start.)_
- [ ] **P11-02** Write `RUNBOOK.md` — how to start it, deploy it, roll back, read logs, reset
      a password, and what to do when the job queue backs up.
- [ ] **P11-03** **Architecture walkthrough** with Haseeb and Muttayab: why ports and adapters,
      why deterministic scoring, why the worker is separate, how the score is computed.
      **They present this, not Zohaib.**
- [ ] **P11-04** Admin panel training: review an identity, resolve an appeal, publish a
      scoring-model version.
- [ ] **P11-05** **Viva preparation** — rehearse the hard questions until the answers are fluent.
- [ ] **P11-06** Agree the **support window in writing** — what gets fixed, for how long, and
      what counts as new work.

---

## Track D — The report (9 days, Haseeb + Muttayab, runs throughout)

**Owned by the students since 12 August.** Zohaib supplies technical content, diagrams and
measured numbers; they write and present it, because they defend it at viva.

Do not leave this to the end. D-01, D-03 and D-04 can start **now** — they describe what is
already built.

- [ ] **D-01** Update the **SRS** to match what was actually built — especially the scope
      correction: TrustLens scores **enrolled** sellers and returns "no record" for everyone else.
- [ ] **D-02** Correct the "within seconds" claim: score _reads_ are sub-second; _enrollment
      verification_ takes 30–60 seconds. State both.
- [ ] **D-03** Design documents: use-case diagrams, DFDs (levels 0–2), sequence diagrams for
      the verification and scoring flows.
- [ ] **D-04** **ER diagram** for all 40 tables — run `make erd`.
- [ ] **D-05** Test documentation: test cases, results, coverage summary, the Phase 1 accuracy
      numbers, the Phase 7 model metrics. _(Waits on Stage 1 and Stage 2.)_
- [ ] **D-06** Final report chapters: introduction, literature review, methodology,
      implementation, results, conclusion.
- [ ] **D-07** **Limitations chapter** — no NADRA verification, device fingerprinting is
      60–80% accurate, VPN ≠ fraud, non-commercial model licences, SMS constrained by PTA
      registration. Stating limits honestly reads as maturity, not weakness.
- [ ] **D-08** **Future Scope chapter** — reverse-image stolen-photo detection, chat scam
      detection, buyer scam-report feedback loop, marketplace integrations, reputation
      history, mobile app.
- [ ] **D-09** Final presentation deck and demo video.

---

## Decisions still open

1. **Final submission date.** Without it, the remaining ~24 software days map to no calendar.
   Sequencing above is by dependency, so it survives any date — but Stages 6 and 7 compress
   under pressure and **Stage 3 cannot**.
2. **P0-12 approach** — internal route (recommended) or first-party key for `apps/web`.
3. **MFA** — build it or document the omission (P4-09).
4. **The $3–4/month for the worker instance** — who pays, and on whose card.

---

## Scoreboard

Update this as boxes get ticked. It is the one line to show the students each week.

| Stage | Title            |  Tasks | Done   | Owner             |
| ----- | ---------------- | -----: | ------ | ----------------- |
| 0     | Corrections      |      7 | **7**  | Zohaib ✅         |
| 1     | Accuracy numbers |      7 | 0      | Students → Zohaib |
| 2     | Scam classifier  |      9 | **7**  | Zohaib 🔴 data    |
| 3     | Deploy           |     15 | 0      | Zohaib            |
| 4     | Admin panel      |      8 | 0      | Zohaib            |
| 5     | Seller leftovers |      4 | 0      | Zohaib            |
| 6     | QA and demo      |      8 | 0      | Zohaib            |
| 7     | Handover         |      6 | 0      | Both              |
| D     | Report           |      9 | 0      | Students          |
|       | **Total**        | **73** | **14** |                   |

_Created 22 August 2026 · Sequenced by dependency, not by date · Scope: academic FYP_
