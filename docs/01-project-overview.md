# 01 — Project Overview

## 1. Problem statement (from the proposal)

> Online marketplace buyers are frequently scammed by fake seller profiles, stolen photos, throwaway phone
> numbers and emails, multiple accounts created from one device, and unrealistic "too good to be true"
> listings, with no reliable way to judge a seller before paying.

Each of those five fraud patterns maps to a defence in the system. This mapping is the spine of the whole
architecture — every table, job, and endpoint traces back to a row here.

| Fraud pattern in the proposal          | Defence                                                                               | Signal family       | Where implemented                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------------- | ------------------- | ---------------------------------------------------------------------- |
| Fake seller profiles                   | CNIC OCR + selfie face match                                                          | `IDENTITY`          | `worker` OCR/face jobs, `identity_documents`, `identity_verifications` |
| Stolen photos                          | Image hashing groundwork (pHash stored now); reverse-image search is **future scope** | `LISTING`           | `listing_images.perceptual_hash`                                       |
| Throwaway phone numbers                | OTP + VOIP/disposable-carrier lookup                                                  | `PHONE`             | `phone_numbers`, OTP flow                                              |
| Throwaway emails                       | Verification link + disposable-domain + domain-age check                              | `EMAIL`             | `email_addresses`                                                      |
| Multiple accounts from one device      | Device fingerprint clustering + IP/VPN reputation                                     | `DEVICE`, `NETWORK` | `devices`, `user_devices`, `ip_addresses`, `access_events`             |
| "Too good to be true" listings         | LLM analysis + custom-trained scam classifier + price anomaly                         | `LISTING`           | `listing_analyses`, `apps/ml`                                          |
| No reliable way to judge before paying | Explainable 0–100 Trust Score + public API                                            | —                   | `trust_scores`, `trust_score_signals`, `/public/v1`                    |

## 2. Objective (verbatim scope from the proposal)

- Sellers complete **identity, phone, email, and device checks**.
- The system **analyzes each listing with AI**.
- All signals combine into **a single Trust Score (0–100) with a clear risk level and the reasons behind it**.
- A **REST API** lets marketplaces request a seller's score.

**Expected outcome:** _"A working web application and API that return an explainable seller Trust Score
within seconds, clearly showing why a seller is low, medium, or high risk."_

## 3. Features in scope (7th–8th semester)

| #   | Feature                                         | Notes                                                                                  |
| --- | ----------------------------------------------- | -------------------------------------------------------------------------------------- |
| F1  | Identity verification — CNIC OCR + face match   | OpenCV preprocessing → EasyOCR text extraction → DeepFace selfie↔CNIC-photo comparison |
| F2  | Phone OTP verification                          | 6-digit code, rate-limited, hashed at rest, expiry + attempt cap                       |
| F3  | Email verification & checks                     | Signed token link, disposable-domain list, MX/domain-age lookup                        |
| F4  | Device & IP / VPN detection                     | Client fingerprint + server-side IP intelligence                                       |
| F5  | AI listing analysis                             | LLM (OpenAI/Claude) structured extraction + custom-trained scam-listing classifier     |
| F6  | Explainable Trust Score engine with risk levels | Versioned weighted rules, per-signal breakdown, hard caps                              |
| F7  | Admin and appeal panel                          | Review queue, manual override with mandatory justification, appeal threads, audit log  |
| F8  | Public Trust Score API                          | API-key auth, scoped, rate-limited, cached, documented via OpenAPI                     |

## 4. Explicitly out of scope (proposal lists these as _Future Scope_)

Reverse-image stolen-photo detection · chat scam-detection · direct marketplace integrations ·
reputation history · mobile version.

The architecture leaves **seams** for each of these (see [19 — Future Improvements](19-future-improvements.md))
but ships none of them. Building seams is cheap; building unrequested features is not.

## 5. Target users → personas

From the proposal: _"Online buyers, marketplace platforms (OLX-style), rental and property portals,
second-hand vehicle sites, and freelance / peer-to-peer commerce platforms."_

| Persona                    | Role in system         | Primary need                                                                                 |
| -------------------------- | ---------------------- | -------------------------------------------------------------------------------------------- |
| **Buyer**                  | `BUYER` (or anonymous) | Look up a seller before paying; understand _why_ the score is what it is                     |
| **Seller**                 | `SELLER`               | Get verified quickly; see what is lowering their score; appeal a wrong result                |
| **Marketplace integrator** | API client (machine)   | Fetch a seller's score server-to-server, low latency, high availability                      |
| **Reviewer**               | `REVIEWER`             | Work the flagged-seller queue; approve/reject identity documents                             |
| **Admin**                  | `ADMIN`                | Everything a reviewer can do, plus tune scoring weights, manage API clients, override scores |

Full permission matrix: [09 — User Roles](09-user-roles.md).

## 6. Technology stack (as mandated by the proposal)

| Layer           | Technology                                                                                             | Source                                     |
| --------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| Frontend        | React.js / **Next.js**, **Tailwind CSS**                                                               | Proposal                                   |
| Backend         | **Python**, **FastAPI**                                                                                | Proposal                                   |
| Database        | **PostgreSQL**                                                                                         | Proposal                                   |
| Cache           | **Redis**                                                                                              | Proposal ("PostgreSQL (with Redis cache)") |
| AI              | **OpenAI / Claude API**, **OpenCV**, **EasyOCR**, **DeepFace**, custom-trained scam-listing classifier | Proposal                                   |
| Frontend deploy | **Vercel**                                                                                             | Proposal                                   |
| Backend deploy  | **Railway**                                                                                            | Proposal                                   |
| Tools           | VS Code, **Postman**, **Figma**, **Git & GitHub**                                                      | Proposal                                   |
| Platform        | Web, cross-platform browsers (Windows / Linux / macOS)                                                 | Proposal                                   |

Nothing above is substituted. Everything _added_ (ARQ, SQLAlchemy, Alembic, pnpm, Turborepo, Playwright,
object storage, an SMS provider) is either an unavoidable implementation detail of a mandated technology
or is recorded as an assumption in §7.

## 7. Assumptions register

The proposal is four pages; these gaps are filled with the most defensible choice and flagged so a
supervisor can overrule any single one without disturbing the rest of the design.

| #   | Gap in the proposal                            | Assumption                                                                                                                                 | Blast radius if changed                                  |
| --- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------- |
| A1  | Risk-band thresholds for "low / medium / high" | **0–39 High, 40–69 Medium, 70–100 Low risk**                                                                                               | One config row in `scoring_models`                       |
| A2  | "CNIC" not expanded                            | Pakistani **Computerized National Identity Card**; OCR targets front (name, CNIC number, DOB, photo) and back (address, issue/expiry)      | OCR field templates only                                 |
| A3  | How sellers enter the system                   | Self-registration on TrustLens **plus** partner-initiated onboarding via the public API                                                    | Adds `/public/v1/sellers` POST                           |
| A4  | How listings reach TrustLens                   | Seller submits a listing **URL or manual form**; no marketplace crawling (that is future scope)                                            | `listings.source` enum already has `API`/`IMPORT` values |
| A5  | Auth mechanism                                 | Email+password, **JWT access token (15 min) + rotating refresh token in an httpOnly cookie**                                               | [07](07-authentication-authorization.md)                 |
| A6  | Where CNIC/selfie images are stored            | **S3-compatible object storage** (Cloudflare R2 / Supabase Storage / Railway volume), never in Postgres, never public                      | `trustlens-shared` storage adapter                       |
| A7  | IP / VPN intelligence source                   | A third-party IP-reputation API behind a port, with an offline ASN/datacenter-list fallback so the FYP demo works without a paid key       | One adapter                                              |
| A8  | OTP delivery                                   | SMS provider (e.g. Twilio) behind a `SmsSender` port; console sender in dev                                                                | One adapter                                              |
| A9  | Transactional email                            | Email provider (e.g. Resend/SendGrid) behind an `EmailSender` port; MailHog in dev                                                         | One adapter                                              |
| A10 | Admin panel deployment                         | **Same Next.js app** under a `(admin)` route group, not a separate deployment                                                              | Route group only                                         |
| A11 | Scam-classifier training data                  | Bootstrapped from a hand-labelled dataset of scam/genuine listings assembled by the team; the pipeline lives in `apps/ml` and is versioned | `apps/ml`                                                |
| A12 | Localisation                                   | English UI, i18n-ready structure, no second locale shipped                                                                                 | `packages/i18n` seam                                     |
| A13 | Multi-tenancy                                  | Partner marketplaces are **API clients**, not tenants; there is one shared seller graph                                                    | `marketplaces` table                                     |
| A14 | Score freshness                                | A score is valid for **30 days** or until an input signal changes, whichever comes first                                                   | `trust_scores.valid_until`                               |
| A15 | Payments / billing                             | Out of scope; API quota is enforced but not billed                                                                                         | —                                                        |

> **WHY a register instead of inline guesses:** an FYP is graded partly on defending decisions. Every
> ambiguity is visible in one table with its cost of reversal, so a supervisor's feedback becomes a
> one-line change rather than a redesign.

## 8. Recommended build order (8th semester)

Ordered so that something demonstrable exists at every checkpoint.

| Sprint | Deliverable                                                                                                          | Unblocks           |
| ------ | -------------------------------------------------------------------------------------------------------------------- | ------------------ |
| S1     | Monorepo scaffold, CI, Docker Compose (Postgres+Redis+MailHog+MinIO), migrations, auth (register/login/refresh/RBAC) | Everything         |
| S2     | Seller profile, email verification, phone OTP, device+IP capture                                                     | Signals 2–5        |
| S3     | File upload pipeline + CNIC OCR (OpenCV+EasyOCR) + face match (DeepFace) as ARQ jobs                                 | Signal 1           |
| S4     | Listing CRUD + LLM listing analysis + baseline classifier                                                            | Signal 7           |
| S5     | Scoring engine v1, breakdown persistence, seller dashboard, public buyer score page                                  | F6 — **core demo** |
| S6     | Public API: clients, API keys, quotas, caching, OpenAPI docs, Postman collection                                     | F8                 |
| S7     | Admin panel + appeals workflow + audit log                                                                           | F7                 |
| S8     | Hardening: rate limits, security review, Playwright E2E, load test, deploy to Vercel+Railway, report                 | Final presentation |

## 9. Non-functional requirements

Derived from the proposal's "within seconds" outcome and from ordinary production expectations.
These are the targets the architecture is sized for; they are _not_ claims of measured performance.

| ID    | Requirement                                 | Target                                                                             |
| ----- | ------------------------------------------- | ---------------------------------------------------------------------------------- |
| NFR-1 | Public score read latency                   | p95 < 150 ms (Redis-cached), p99 < 400 ms                                          |
| NFR-2 | Score computation after last signal arrives | < 5 s median (excludes human review)                                               |
| NFR-3 | CNIC OCR + face-match job duration          | < 30 s p95                                                                         |
| NFR-4 | Explainability                              | Every score exposes ≥1 reason per contributing signal                              |
| NFR-5 | Auditability                                | Every score, override, and admin action is reconstructable from the DB             |
| NFR-6 | Availability of the public API              | Degrades to last-known-good cached score if the DB is unavailable                  |
| NFR-7 | PII protection                              | CNIC images and biometric data encrypted at rest, access-logged, retention-bounded |
| NFR-8 | Portability                                 | Runs fully offline via Docker Compose with no paid third-party key                 |

NFR-8 matters more than it looks: an FYP must be demonstrable on a lab machine with no internet. Every
external dependency therefore sits behind a port with a local fake ([15 §9](15-security.md)).
