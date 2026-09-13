# TrustLens Marketplace v2 — Target Flow & End Product

**What this file is.** A plain description of the complete product we are building toward, per
the "TrustLens Software Feature Requirements & Developer Delivery Specification" (Mam Misbah,
08 Sep 2026). It describes the **target end state** — every screen, every journey, what the
finished app does — not what exists today. For current build status against this target, see
[`MARKETPLACE_TRACKING.md`](MARKETPLACE_TRACKING.md).

This is a different, larger document than [`REMAINING.md`](REMAINING.md)/[`TASKS.md`](TASKS.md),
which track the original academic FYP scope (SRS-defined, supervisor-agnostic, 22 Aug baseline).
This new spec is a formal client/supervisor handoff document that expands TrustLens from "a
Trust Score lookup tool" into a full local marketplace with OLX-style browsing, favourites,
in-app chat, curated safe meetups, and — the hardest part — **live, anti-spoof identity capture**
that goes well beyond a single selfie.

---

## 1. One-paragraph vision

A buyer opens TrustLens the way they'd open OLX or Facebook Marketplace: browse by category,
search, filter by area and price, save favourites, message a seller, agree a deal, and meet
somewhere safe — except every seller carries a Trust Score computed from **verifiable** evidence
(a live camera capture that proves a physical CNIC was held by a live person, not a photo of a
photo), and every risky moment in the flow (advance-payment pressure, an unlisted meetup, a
too-good-to-be-true price) is called out before money or trust changes hands.

---

## 2. Roles

| Role                  | Can do                                                                                                                                                                       |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Guest**             | Browse, search, view listings/storefronts, view a seller's public Trust Score. Cannot favourite, chat, or make offers — redirected to login/register at the point of action. |
| **Buyer**             | Everything a guest can, plus: favourite, saved searches + alerts, chat, offers, SafeMeet, reports, reviews.                                                                  |
| **Individual Seller** | Everything a buyer can, plus: create/manage listings, go through identity verification, hold a Trust Score, respond to appeals.                                              |
| **Business Seller**   | Everything an individual seller can, plus: business profile, branches, team roles, separate business verification evidence, follower count.                                  |
| **Reviewer**          | Staff. Works identity-review, listings-moderation, reports, SafeMeet, and dispute queues. No score-override power.                                                           |
| **Administrator**     | Everything a reviewer can, plus: scoring-model authoring/activation, staff account management, maker/checker approval on high-risk decisions, full audit access.             |

Staff (Reviewer/Administrator) access requires **MFA** in production — this is a hard requirement
of this spec (FR-16), and it currently conflicts with a decision made in the FYP-scope session:
MFA was left **unbuilt and explicitly disabled by default** to prevent a lockout, rather than
implemented. Building real MFA enrollment is now in scope for this spec (see tracking file,
Phase 0 / BLK-04).

---

## 3. Site map — every screen the finished product has

**Public / guest-visible**

- `/` — landing page, brief Trust Score pitch
- `/marketplace` — main browse feed: Fresh / Featured / Nearby / Recently Viewed sections
- `/search?q=&category=&area=&...` — full search + filter + sort, state lives in the URL
- `/categories/[slug]` — category landing, same filter/sort surface scoped to one category
- `/listings/[id]` — product detail: gallery, price, condition, area/map, seller card, actions
- `/sellers/[handle]` — public seller storefront: active/sold listings, Trust Score, reviews
- `/terms`, `/privacy`, `/safety`, `/community-guidelines`, `/report-issue`, `/contact` — legal/trust pages

**Buyer (authenticated)**

- `/favorites` — saved listings, remove/share/compare
- `/favorites/searches` — saved searches with alert frequency controls
- `/chat` and `/chat/[conversationId]` — conversation list + thread (messages, offers, SafeMeet proposals)
- `/offers` — sent/received offers and their status
- `/meetups` — proposed/accepted SafeMeet plans
- `/notifications` — event feed + per-channel preference settings
- `/reports/[id]` — status of a report the user filed

**Seller (authenticated, individual or business)**

- `/dashboard` — verification checklist, Trust Score, listings summary
- `/dashboard/listings`, `/dashboard/listings/new`, `/dashboard/listings/[id]/edit` — CRUD + media upload + AI-analysis status
- `/dashboard/trust-score` — score, signal breakdown, appeal
- `/dashboard/verify/identity` — the live capture flow (see §5 below — this is the hardest screen in the product)
- `/dashboard/verify/phone`, `/dashboard/verify/email` — OTP / link flows
- `/dashboard/business` (business sellers only) — business profile, branches, team roles, tax/registration evidence
- `/dashboard/settings` — password, sessions, data export, account deletion

**Staff (Reviewer / Administrator, separate app)**

- `/reviews` — identity-review, fraud-flag, appeal, device-cluster queues (exists today)
- `/reviews/listings` — **new**: listings-moderation queue
- `/reviews/reports` — **new**: user-filed reports queue
- `/reviews/safemeet` — **new**: SafeMeet location verification/incident queue
- `/reviews/disputes` — **new**: transaction dispute queue
- `/sellers`, `/sellers/[id]` — seller search, detail, signal breakdown, evidence viewer (exists today)
- `/scoring` — scoring-model versions, authoring, activation (exists today)
- `/admin/mfa` — **new**: staff MFA enrollment

---

## 4. Core journeys, end to end

### 4.1 Guest → Buyer discovery

Guest lands on `/marketplace`, sees Fresh/Featured/Nearby sections (Nearby needs a location —
prompted or defaulted). Searches "iphone 13" → `/search?q=iphone+13`, narrows by City=Lahore,
Area=DHA, Price≤150000, sorts by Trust Score. Clicks a card → `/listings/[id]`: gallery, seller's
Trust Score badge, approximate area on a map circle (never an exact address). Clicks the heart →
redirected to `/login?next=/listings/[id]`, logs in, lands back on the same listing, favourite
is now saved.

### 4.2 Buyer → Seller conversation → Safe meetup → Completed transaction

From `/listings/[id]`, buyer clicks **Chat Safely** → a conversation opens bound to an immutable
snapshot of the listing (title/price/condition at that moment, so a later price edit can't be
used to dispute what was agreed). Buyer sends a message, then an **offer card** (amount +
expiry). Seller counters or accepts; an accepted offer can reserve the listing. Either party
proposes **SafeMeet**; the platform suggests 3–5 verified public spots near both parties'
approximate areas (never home addresses); both must accept the _same_ place and time. On the
day, an optional short-lived QR check-in confirms handover. Transaction moves through
Initiated → Agreed → Meetup Planned → Handed Over → Completed. If something goes wrong at any
point, either party can **Report** or **Block**, which opens a staff case without deleting the
evidence trail.

### 4.3 Seller onboarding and identity verification (the hard part)

A buyer decides to sell, chooses Individual or Business, and reaches
`/dashboard/verify/identity`. This is a ten-step sequence (detailed in §5) that a static file
upload can no longer satisfy in production — every step needs a live camera and, for two of the
steps, a randomized challenge the system issues in real time. The seller ends the flow with one
of three outcomes: **Passed**, **Retry Required**, or **Manual Review** — never a raw confidence
number. A Trust Score then computes from this plus phone/email/device/listing signals, and the
seller can appeal any one signal if they believe it's wrong.

### 4.4 Business seller

A business seller additionally provides a business profile (name, branches, applicable
registration/tax evidence) and invites team members with scoped roles. Business verification is
tracked **separately** from the individual's personal identity verification — a business badge
cannot be earned on personal CNIC evidence alone. The storefront shows follower count,
transaction count, response rate, and blind two-sided reviews (both buyer and seller review each
other; the reviews only reveal once both have submitted or a window expires).

### 4.5 Staff operations

A reviewer signs in with MFA, works the identity-review queue (CNIC/selfie via short-lived
signed URLs, never a permanent public link), and separately handles listings-moderation,
user reports, SafeMeet incidents, and transaction disputes — each its own queue with its own
SLA. High-risk decisions (e.g. reversing a Trust Score, banning a business) go through a
maker/checker step: one staff member proposes, a second approves, both logged immutably.

---

## 5. The identity verification sequence, in full

This is the single most technically demanding part of the spec (FR-08/FR-09) and the part of the
current codebase furthest from this target — today's build is one CNIC-front photo, one
CNIC-back photo, one selfie photo (with a gallery-upload fallback), and a face-similarity score.
The target sequence is:

| #   | Screen/service          | Required result                                                                                                                                                                                                            |
| --- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Consent & readiness     | Policy version recorded, camera permission granted, device/session checks pass                                                                                                                                             |
| 2   | Live CNIC front         | Frame detection, all 4 corners, glare/sharpness check, auto-capture (no manual shutter, no gallery picker)                                                                                                                 |
| 3   | Live CNIC back          | Same quality bar; barcode/text checks if applicable                                                                                                                                                                        |
| 4   | **Document liveness**   | A randomized prompt ("tilt the card slightly", "move it closer") drives motion/texture/reflectance analysis to prove a _physical_ card is in front of the camera — not a screenshot, printed photo, or a photo of a screen |
| 5   | **Hold ID beside face** | Full face **and** all 4 card corners visible simultaneously; a randomized server-issued code or instruction must be followed before auto-capture triggers                                                                  |
| 6   | **Face liveness video** | A short prompted video (randomized movement/lighting cues), distinct from step 5's still frame                                                                                                                             |
| 7   | OCR & face match        | Front/back field consistency; the liveness reference frame (not the holding-ID photo) is what's compared to the CNIC portrait                                                                                              |
| 8   | Decision                | **Passed** / **Retry Required** / **Manual Review** — the only three states a user ever sees                                                                                                                               |
| 9   | Trust update            | Signed signals (document liveness, face liveness, face match, holding-ID) feed an async score recompute, each with a model/provider version and reason code                                                                |
| 10  | Retention               | Raw capture media is deleted at the policy deadline; only the minimal audited _result_ survives                                                                                                                            |

**Hard rule carried through every step:** possession of the ID (holding it up) is not proof of
liveness by itself, and liveness of the document is not proof of liveness of the face — these are
three separate, separately-scored checks (document liveness, face liveness, face-match), and a
system that only does one of them (today's system only does face-match) has not met this
requirement.

**Explicitly forbidden**, per the spec:

- No gallery/file picker for CNIC or selfie capture in production — camera-only, or a declared,
  accessible non-camera manual-review path (not a silent fallback).
- No exposing raw liveness/face-match confidence numbers to the end user — only Pass/Retry/Manual
  Review, ever.
- No claiming NADRA (government registry) verification without an actual authorized integration
  — this system checks document _plausibility_ and _face match_, nothing more, and must say so.
- No indefinite storage of raw camera captures — a retention job must exist and actually run.

---

## 6. Non-functional bar (applies to every feature above)

- **Security** — TLS everywhere, secrets server-only, encryption at rest for biometric data,
  short presigned-URL expiry, RBAC + MFA for staff, CSRF/CORS, rate limits, malware scanning on
  uploads, immutable audit log for every sensitive action.
- **Privacy** — data minimization by default; public listing/seller data carries only an
  approximate area, never a home address or exact coordinate; no raw OTP/token/biometric score
  ever reaches a public client; export/delete/access rights are real, working features, not
  aspirational copy.
- **Performance** — search p95 under 500ms at the agreed demo load; favourite toggle feels
  instant (optimistic UI, rollback on failure); images lazy-load with thumbnails.
- **Reliability** — every write that can be double-submitted (favourite, OTP request, offer,
  notification) is idempotent; failed jobs retry or land in a dead-letter queue instead of
  silently vanishing.
- **Accessibility** — full keyboard navigation, 44px minimum touch targets, visible focus states,
  sufficient contrast, reduced-motion support, and — critically for identity verification — a
  genuine non-camera fallback path for anyone who cannot complete a live capture.
- **Observability** — every request carries an ID; the identity-verification funnel, upload
  failures, provider webhook callbacks, and worker/queue health are all visible to operations,
  not just to a developer tailing logs.

---

## 7. What "done" looks like, walked through once

A buyer in Lahore opens TrustLens on their phone, searches "used sofa", narrows to DHA within
5km, and finds one from a seller whose Trust Score badge shows **LOW risk, 91/100** with a
"why" breakdown one tap away. They favourite it, then message the seller — the app warns them
once, gently, not to pay an advance before inspecting. They agree a price via an offer card,
propose a SafeMeet at a platform-suggested public spot, both accept the same time, and complete
the handover with a quick QR scan. Afterward, both leave a blind review that reveals once both
are in. Nothing about this differs from a well-built OLX clone — until you look at _why_ the
seller's score is 91 and not simply "trusted because they said so": it's because thirty seconds
of live camera work, that a photo or a hired stand-in cannot fake, said so.
