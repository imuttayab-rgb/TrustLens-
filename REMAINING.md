# TrustLens — What's left, in order

**Companion to [`TASKS.md`](TASKS.md).** That file is the full history of the project,
including everything already finished. This file is the short version: only what is
**not done**, arranged in the order it should be done.

Task IDs are the same in both files. Tick a box here, tick it in `TASKS.md` too.

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked on someone else

---

## Where we are

|                         |                                                     |
| ----------------------- | --------------------------------------------------- |
| Software track          | ~37 of 44 days done — **about 84%**                 |
| Documentation track (D) | 8 of 9 days done — **about 89%** (deck/video open)  |
| **Whole FYP**           | **about 85%**                                       |
| Phases finished         | 0, 3, 5, 6, most of 2, 4, 7, D                      |
| Phases untouched        | Stage 1 (blocked on students), D-09 (deck/video)    |
| Extra scope, done       | A full client-driven marketplace expansion — see    |
|                         | **Stage 4b** below — none of it was in the original |
|                         | 72-task plan                                        |

The hard part is behind us, and since 22 Aug the admin panel, the seller-side leftovers, and
the entire report documentation package have all landed too. Two real gaps remain in the admin
panel (below), one stub in account deletion, and Stage 1's accuracy numbers are still waiting
on the students to supply test images. Everything else left is calendar, not risk.

---

## Stage 0 — Corrections first ✅ done 22 Aug

- [x] **P0-12** Fix the public buyer page 404.
- [x] **P0-16** 🚨 Startup route guard was checking almost nothing — fixed.
- [x] **P0-17** 🚨 Every reason on the buyer page was labelled "Identity" — fixed.
- [x] **P0-18** Three e2e tests could never have passed — fixed, suite 7/7 green.
- [x] **P10-06** Fixed the stale documentation.
- [x] **P0-19** 🚨 CI's Prettier gate had never passed — fixed.
- [x] **P0-15** Corrected the stale boxes in `TASKS.md`.

_(Full detail on each item is unchanged from the 22 Aug version — see `TASKS.md` for the
complete writeup of Stage 0.)_

---

## Stage 1 — Unblock the accuracy numbers (students, still not started)

**Still stuck. This is the only thing left that Zohaib cannot do alone**, and it has been
stuck since week 1. Without it there are no accuracy figures for the results chapter — the
Test Cases document already flags this honestly rather than papering over it.

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
      on the same images, and choose on measured accuracy.
- [ ] **P1-08** Enable anti-spoofing; test against a printed photo and a phone-screen photo.
- [ ] **P1-09** Record which pretrained weights are downloaded and their licences → feeds P7-08.
- [ ] **P1-10** Confirm model download size and cold-start time.

---

## Stage 2 — The scam classifier ✅ built 22 Aug · 🔴 still blocked on data

Nothing changed here since 22 Aug — still gated on 300–500 hand-labelled Pakistani ads
(**P7-02**), which is a human-labelling task, not a code task. See `TASKS.md` for the full
metrics table and writeup. **Still do not enable this as a live scoring input** — the false
positive rate on real Pakistani marketplace ads (1 of 7 scams caught) would flow straight
into sellers' trust scores.

- [x] P7-01, P7-03, P7-05, P7-06, P7-07, P7-08, P7-09 — done.
- [~] **P7-02** 🔴 Datasets — proxies done, local ads still needed. **Gates the phase.**
- [~] **P7-04** DistilBERT — script ready, not run (needs a Colab GPU).

---

## Stage 3 — Production ready, locally ✅ 22 Aug

No change since 22 Aug. Still open, and all of it needs accounts rather than code:

- [ ] **P8-01 / P8-02** Resend account + SPF/DKIM/DMARC on a real domain. **Partially
      unblocked**: Resend is wired up and sending from the sandbox address
      (`onboarding@resend.dev`), but that sandbox only delivers to the Resend account owner's
      own email — a verified domain is still needed before real users receive mail.
- [ ] **P8-03** Twilio trial for SMS OTP. **Partially unblocked**: a real Twilio account is
      now configured (SID/token/from-number wired into `.env`), but the from-number is still
      a personal number, not a Twilio-purchased one — OTP SMS will not actually send until a
      real Twilio number is bought.
- [ ] **P8-04** IP/VPN detection API key. Offline heuristics are the default.
- [ ] **P9-01 → P9-06** A public host, if and when the students want one.

---

## Stage 4 — Admin panel (Phase 4 remainder) — mostly done, 2 real gaps open

**Re-verified against actual code, not commit messages, on 12 Sep.** Five of eight items are
genuinely done with real DB-backed logic. Two are partially done. One (MFA) is decided but
has a latent production-config risk worth fixing before handover.

- [x] **P4-01b** Seller-search use case + endpoint — done.
- [x] **P4-04** Seller list: search, filter by risk band and flag status, pagination — done.
- [~] **P4-05** Seller detail — **partial.** Has verification history and score history.
  **Missing:** a per-signal score breakdown, and an evidence viewer reachable outside the
  review-queue context (CNIC/selfie can currently only be viewed while a review is
  in-flight, not from the seller-detail page itself).
- [x] **P4-06** Manual identity review — CNIC and selfie via short-lived signed URLs,
      approve/reject with reason — done.
- [x] **P4-03b** Dashboard counts by risk band, pending reviews, recent flags — done.
- [~] **P4-07** Scoring-model admin — **partial.** Can view pre-seeded model versions and
  activate one (correctly preserving version-pinning on historical scores). **Missing:**
  any way to actually author or edit weights and publish a new version — the
  `scoring_model:write` / `scoring_model:simulate` permissions and the repository's
  `create`/`update` methods exist but are dead code, never called by any endpoint.
- [x] **P4-08** Audit trail — every admin action recorded with actor, timestamp, before/after,
      with real call sites across the codebase — done.
- [x] **P4-09** MFA decision — documented (staff MFA is not implemented; setting exists,
      feature does not). **🚨 Found while re-verifying:** `SECURITY_MFA_REQUIRED_ROLES`
      defaults to `ADMIN,REVIEWER` with zero MFA enrollment endpoint anywhere in the codebase.
      A production deploy that doesn't explicitly empty this setting would **lock every
      admin/reviewer out of login**, since the system would demand a second factor nobody can
      ever enroll in. Fix before go-live: either implement enrollment, or default the setting
      empty and document why.

_Stage done when:_ the seller-detail evidence gap and the scoring-model authoring gap are
closed, and the MFA setting's default is corrected.

---

## Stage 4b — Client-driven marketplace expansion (extra scope, done this session) ✅

**None of this was in the original 72-task FYP plan.** The client (acting through the
students) sent two rounds of feedback after the product was already functional, asking for
consumer-marketplace features on top of the trust-verification core. All of it is built,
tested (mypy/ruff/pytest/tsc/eslint all green, 348 backend tests passing), committed and
pushed. It has **no dedicated test coverage yet** — see Stage 6.

**Round 1 — bug fixes (translated client reports, all confirmed and fixed):**

- [x] Google OAuth sign-in — full authorization-code flow, auto-verified accounts.
- [x] Selfie capture now uses the live camera, not a gallery file picker.
- [x] Swagger/OpenAPI docs closed in non-dev environments.
- [x] Email verification re-enabled (had been silently disabled).
- [x] Header navigation straightened; sell-flow wording and image-order fixed.
- [x] Public listing catalog with categories and search.
- [x] Favorites/wishlist.

**Round 2 — feature requests ("Do work on this" — all five delivered):**

- [x] OLX-style area/city selection on listings.
- [x] Map integration — **not** Google Maps (client rejected the $0-then-$30-prepay billing
      model); built on **Leaflet + OpenStreetMap** instead, which needs no API key and has no
      billing tier at all.
- [x] Search, filters (price, location, category) and sorting on the public catalog.
- [x] Terms, privacy and help pages (closing the "Legal/help completion" ask).
- [x] Buyer↔seller chat — simple threaded messaging, per the scope the client confirmed.

**Follow-on, added while finishing the above:**

- [x] Public listing detail page (`/listing/[id]`), server-rendered, mirroring the existing
      seller-page SEO pattern — buyer catalog cards now open a real listing page instead of
      jumping straight to the seller's trust-score page.

---

## Stage 5 — Seller-side leftovers — mostly done, 1 real gap open

**Re-verified against actual code on 12 Sep.**

- [x] **P2-22** Public buyer page polish — done, genuine responsive Tailwind breakpoints
      verified at 360px and 1440px.
- [x] **P3-05** Listing image upload + `imagehash` duplicate detection — done, real
      SHA-256 + perceptual (dhash) hashing with actual Hamming-distance duplicate checks.
- [~] **P2-23** Account settings — **partial.** Change-password and active-sessions
  management are fully real and functional. Delete-account shares the same stub as
  P2-24 below.
- [~] **P2-24** Data export and deletion — **partial.**
  - Data export genuinely returns real data, but it's minimal: only `user` and
    `seller_profile` rows. Listings, verification records and sessions are not included.
  - 🚨 **Account deletion is a fake stub.** `apps/worker/src/trustlens_worker/jobs/maintenance.py`'s
    `purge_account()` job only logs `"account_purged"` and returns `{"purged": True}` — it
    does not delete a single database row. Contrast with the neighbouring `publish_outbox`
    job in the same file, which is fully implemented. A user who requests deletion today gets
    told it happened and nothing happens.

_Stage done when:_ `purge_account()` actually deletes (or anonymizes, per the data-retention
decision the report should state) the user's rows, and data export covers listings and
verification records too.

---

## Stage 6 — QA and demo readiness (Phase 10) — still the main risk area

Test Cases doc (`fyp-submission/docs/05-Test-Cases.md`) now honestly states **26 of 51
specified test cases executed (~51%)** — a real, documented number, not a guess. Automated
coverage is still thin, and **none of Stage 4b's new marketplace features have any test
coverage** (no unit, integration, or e2e tests for OAuth, catalog/search, favorites, chat,
maps, or the listing detail page).

- [ ] **P10-01** Raise domain test coverage; integration tests for each use case — **now
      includes the untested Stage 4b features above.**
- [ ] **P10-02** Playwright E2E: full seller journey, buyer lookup, admin review, appeal —
      **plus new specs for catalog/search, favorites, chat, and OAuth login.**
- [~] **P10-03** Security pass. Automated checks done 22 Aug (`make prod-security`, 16/16
  pass). **Left:** manual RBAC review, dependency-vulnerability scan, and a look at the
  MFA-lockout risk found in Stage 4 (P4-09).
- [ ] **P10-04** Load-test the public score endpoint; confirm the p95 numbers already
      written into the thesis (§Ch.7) hold up under load, not just in isolation.
- [ ] **P10-05** Cross-browser and cross-device: Chrome, Safari on iPhone, Chrome on Android.
- [ ] **P10-07** Seed a convincing demo dataset — sellers across all three risk bands.
- [ ] **P10-08** Write and **time** the demo script. Rehearse it end to end.
- [ ] **P10-09** Demo fallback plan — recorded video and screenshots. ⚠️ Neon sleeps after
      5 minutes idle; ping it before the demo.

---

## Stage 7 — Handover and training (Phase 11)

- [ ] **P11-01** Transfer credentials and ownership — GitHub, Vercel, Fly, Neon, Upstash, R2,
      Twilio, Resend, and now also the Google Cloud OAuth client.
- [x] **P11-02** `RUNBOOK.md` — done 22 Aug.
- [ ] **P11-03** **Architecture walkthrough** with Haseeb and Muttayab. **They present this.**
- [ ] **P11-04** Admin panel training: review an identity, resolve an appeal, publish a
      scoring-model version — **note this last part isn't possible yet, see P4-07.**
- [ ] **P11-05** **Viva preparation.** `fyp-submission/docs/01-Simple-Guide.md` already exists
      as a first pass at anticipated viva questions — rehearse from it.
- [ ] **P11-06** Agree the support window in writing.

---

## Track D — The report — substantially done ✅ (package generated 10 Sep)

**Major update since 22 Aug.** A full documentation package now exists under
`fyp-submission/docs/`: SRS (IEEE 830), SDD (IEEE 1016), Test Cases (IEEE 829), User Manual,
and an 8-chapter Thesis with front matter, references and 4 appendices — 3,400+ lines across
8 documents, plus real screenshots from the running app, Mermaid diagrams render-tested and
exported to print-quality PNG, and a generated `Project_Thesis.docx` (the actual submission
copy). See `fyp-submission/docs/02-Index.md` for the full map and reading order.

- [x] **D-01** SRS updated to match what was built, scope correction included — done
      (`03-SRS.md`).
- [x] **D-02** "Within seconds" claim corrected: score reads are sub-second, full enrollment
      verification is 30–60s — both figures stated, not conflated (Thesis §7.2, SRS §6.1).
- [x] **D-03** Design documents — use-case diagrams, DFDs, sequence diagrams — done (`04-SDD.md`).
- [x] **D-04** ER diagram and full database schema summary — done (`04-SDD.md`,
      Thesis Appendix B).
- [x] **D-05** Test documentation — done, and **honestly incomplete on purpose**: 26/51 test
      cases marked executed, the rest marked specified-but-not-run rather than faked
      (`05-Test-Cases.md`). Waits on Stage 1 for the accuracy-number rows specifically.
- [x] **D-06** Final report chapters — all 8 written (Intro, Lit Review, Requirements,
      Design, Implementation, Testing, Results, Conclusion) — `07-Thesis.md`.
- [x] **D-07** Limitations chapter — done, stated up front (§1.6) and expanded at the end
      (§8.3): no NADRA verification, device fingerprinting 60–80% accurate, VPN ≠ fraud,
      non-commercial model licences, PTA-constrained SMS.
- [x] **D-08** Future Scope chapter — done (§8.4): reverse-image stolen-photo detection,
      chat scam detection, buyer scam-report loop, marketplace integrations, reputation
      history, mobile app.
- [ ] **D-09** Final presentation deck and demo video — **not started.** Nothing in the
      documentation package addresses this; still the students' to build for the viva.

**Still to do before submission, per the package's own honest checklist** (`02-Index.md` §7):
open the `.docx` in Word and refresh its Table of Contents field (press F9) before printing/
submitting — the rest of the package is otherwise submission-ready today.

---

## Decisions still open

1. **Final submission date.** Without it, the remaining software days map to no calendar.
2. **MFA** — implement enrollment, or default `SECURITY_MFA_REQUIRED_ROLES` empty. This is
   no longer just a documentation decision (P4-09) — leaving it as-is is a real lockout risk.
3. **Data-retention approach for account deletion** — hard delete vs. anonymize. Needed to
   actually implement `purge_account()` (Stage 5), and worth a line in the report regardless.
4. **The $3–4/month for the worker instance, plus now a Twilio number purchase** — who pays.
5. **Scoring-model authoring (P4-07)** — worth building before handover, or documented as a
   known gap the students accept for viva.

---

## Scoreboard

Update this as boxes get ticked. It is the one line to show the students each week.

| Stage | Title                              |  Tasks | Done   | Owner                     |
| ----- | ---------------------------------- | -----: | ------ | ------------------------- |
| 0     | Corrections                        |      7 | **7**  | Zohaib ✅                 |
| 1     | Accuracy numbers                   |      7 | 0      | Students → Zohaib         |
| 2     | Scam classifier                    |      9 | **7**  | Zohaib 🔴 data            |
| 3     | Production local                   |     14 | **10** | Zohaib (2 need accounts)  |
| 4     | Admin panel                        |      8 | **6**  | Zohaib (2 gaps + 1 risk)  |
| 4b    | Marketplace expansion (extra)      |     12 | **12** | Zohaib ✅ (untested)      |
| 5     | Seller leftovers                   |      4 | **2**  | Zohaib (1 stub: deletion) |
| 6     | QA and demo                        |      8 | **1**  | Zohaib                    |
| 7     | Handover                           |      6 | **1**  | Both                      |
| D     | Report                             |      9 | **8**  | Zohaib draft → Students   |
|       | **Total (original 72 + 12 extra)** | **84** | **54** |                           |

_Refreshed 12 September 2026 — re-verified against actual current code (not commit messages
or the stale 22 Aug snapshot) via two independent code-reading passes over Stage 4 and Stage 5. Sequenced by dependency, not by date. Scope: academic FYP + client-driven marketplace
expansion._
