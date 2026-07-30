# 05 — Database Design

PostgreSQL 16 · SQLAlchemy 2.0 (async) · Alembic

## 1. Design conventions (applied to every table)

| Convention | Rule | Reason |
|---|---|---|
| Primary key | `id UUID PRIMARY KEY DEFAULT` (UUIDv7 generated in the app) | Non-enumerable in URLs; time-ordered for index locality |
| Naming | tables `snake_case` plural; columns `snake_case`; FKs `<singular>_id` | Predictability |
| Constraint naming | `pk_`, `fk_`, `uq_`, `ck_`, `ix_` prefixes via SQLAlchemy `naming_convention` | Alembic can autogenerate reliable down-migrations |
| Timestamps | `created_at`, `updated_at` — `TIMESTAMPTZ NOT NULL DEFAULT now()` | Always UTC; `TIMESTAMPTZ` never `TIMESTAMP` |
| Audit | `created_by`, `updated_by` (`uuid NULL REFERENCES users(id)`) on user-mutable tables | Who changed it |
| Soft delete | `deleted_at TIMESTAMPTZ NULL` on business entities only | Never on append-only logs |
| Optimistic locking | `version INTEGER NOT NULL DEFAULT 1` on concurrently-edited rows | Prevents lost updates in the admin panel |
| Money | `NUMERIC(14,2)` + `currency CHAR(3)` | Never floats |
| Enums | Native PG `ENUM` types | Type safety at the DB level; adding a value is a migration, which is the point |
| Semi-structured | `JSONB` for vendor payloads/evidence | Vendor responses evolve; the columns we *score on* are always promoted to real columns |
| Text search | `pg_trgm` GIN indexes on searchable names/titles | Admin search without a search engine |
| Extensions | `pgcrypto`, `pg_trgm`, `citext` | Hashing, fuzzy search, case-insensitive email |

### Soft delete rules

Soft delete applies to `users`, `seller_profiles`, `listings`, `api_clients`, `api_keys`, `appeals`.
It does **not** apply to `trust_scores`, `trust_score_signals`, `audit_logs`, `access_events`,
`api_request_logs`, `webhook_deliveries` — these are the evidence trail; deleting them destroys the
ability to defend a score in an appeal.

Every query on a soft-deletable table filters `deleted_at IS NULL`. This is enforced in one place —
a SQLAlchemy base query filter in the repository layer — not by remembering it at 200 call sites.
Uniqueness under soft delete uses **partial unique indexes**:
`CREATE UNIQUE INDEX uq_users_email ON users (email) WHERE deleted_at IS NULL;`
so a deleted account frees its email for re-registration without a `UNIQUE` violation.

## 2. Enumerations

```sql
CREATE TYPE user_role          AS ENUM ('BUYER','SELLER','REVIEWER','ADMIN');
CREATE TYPE account_status     AS ENUM ('PENDING','ACTIVE','SUSPENDED','BANNED','DELETED');
CREATE TYPE verification_status AS ENUM ('NOT_STARTED','PENDING','PROCESSING','VERIFIED','REJECTED','EXPIRED','FAILED');
CREATE TYPE document_type      AS ENUM ('CNIC_FRONT','CNIC_BACK','SELFIE','PASSPORT','OTHER');
CREATE TYPE risk_level         AS ENUM ('LOW','MEDIUM','HIGH','UNKNOWN');
CREATE TYPE signal_category    AS ENUM ('IDENTITY','PHONE','EMAIL','DEVICE','NETWORK','BEHAVIOUR','LISTING');
CREATE TYPE signal_status      AS ENUM ('PASS','PARTIAL','FAIL','UNAVAILABLE','NOT_APPLICABLE');
CREATE TYPE score_trigger      AS ENUM ('SIGNAL_CHANGE','MANUAL','SCHEDULED','MODEL_CHANGE','API_REQUEST','APPEAL_RESOLUTION');
CREATE TYPE listing_status     AS ENUM ('DRAFT','ACTIVE','ANALYSING','FLAGGED','REMOVED','EXPIRED');
CREATE TYPE listing_source     AS ENUM ('MANUAL','URL_IMPORT','API');
CREATE TYPE appeal_status      AS ENUM ('OPEN','UNDER_REVIEW','NEEDS_INFO','APPROVED','REJECTED','WITHDRAWN');
CREATE TYPE review_status      AS ENUM ('QUEUED','ASSIGNED','APPROVED','REJECTED','ESCALATED');
CREATE TYPE api_key_status     AS ENUM ('ACTIVE','REVOKED','EXPIRED');
CREATE TYPE job_status         AS ENUM ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED','DEAD');
CREATE TYPE file_purpose       AS ENUM ('CNIC_FRONT','CNIC_BACK','SELFIE','LISTING_IMAGE','APPEAL_EVIDENCE','MODEL_ARTIFACT');
CREATE TYPE scan_status        AS ENUM ('PENDING','CLEAN','INFECTED','SKIPPED');
CREATE TYPE consent_type       AS ENUM ('TERMS','PRIVACY','BIOMETRIC_PROCESSING','DATA_SHARING');
CREATE TYPE webhook_event      AS ENUM ('SCORE_UPDATED','SELLER_VERIFIED','SELLER_FLAGGED','APPEAL_RESOLVED');
CREATE TYPE delivery_status    AS ENUM ('PENDING','DELIVERED','FAILED','EXHAUSTED');
CREATE TYPE otp_purpose        AS ENUM ('PHONE_VERIFICATION','LOGIN_MFA','PHONE_CHANGE');
CREATE TYPE token_purpose      AS ENUM ('EMAIL_VERIFICATION','PASSWORD_RESET','EMAIL_CHANGE');
```

## 3. ER diagram (text)

```
                              ┌──────────┐        ┌───────────────┐        ┌─────────────┐
                              │  roles   │◄──────►│  user_roles   │◄──────►│    users    │
                              └────┬─────┘        └───────────────┘        └──────┬──────┘
                                   │                                              │ 1
                          ┌────────▼────────┐                                      │
                          │ role_permissions│                                      │ 0..1
                          └────────┬────────┘                     ┌───────────────▼──────────────┐
                          ┌────────▼────────┐                     │       seller_profiles        │
                          │   permissions   │                     └───┬───┬───┬───┬───┬───┬───┬──┘
                          └─────────────────┘                         │   │   │   │   │   │   │
   users 1─* refresh_tokens                                           │   │   │   │   │   │   │
   users 1─* verification_tokens                                      │   │   │   │   │   │   │
   users 1─* otp_codes                                                │   │   │   │   │   │   │
   users 1─* consents                                                 │   │   │   │   │   │   │
   users 1─* notifications                                            │   │   │   │   │   │   │
   users *─* devices  (via user_devices)                              │   │   │   │   │   │   │
   users 1─* access_events ─* ip_addresses                            │   │   │   │   │   │   │
                                                                      │   │   │   │   │   │   │
     ┌────────────────────────────────────────────────────────────────┘   │   │   │   │   │   │
     │                    ┌───────────────────────────────────────────────┘   │   │   │   │   │
     ▼                    ▼                    ┌──────────────────────────────┘   │   │   │   │
┌─────────────────┐  ┌──────────────────────┐  ▼                  ┌───────────────┘   │   │   │
│identity_documents│ │identity_verifications│ ┌────────────────┐  ▼                   │   │   │
│  * ── files      │ │ (face match result)  │ │ phone_numbers  │ ┌────────────────┐   │   │   │
└─────────────────┘  └──────────────────────┘ └────────────────┘ │email_addresses │   │   │   │
                                                                  └────────────────┘   │   │   │
     ┌────────────────────────────────────────────────────────────────────────────────┘   │   │
     ▼                                                                                     │   │
┌──────────┐ 1─* ┌────────────────┐   1─* ┌──────────────────┐        ┌──────────────┐    │   │
│ listings │────►│ listing_images │       │ listing_analyses │        │ marketplaces │◄───┘   │
└──────────┘     └────────────────┘◄──────└──────────────────┘        └──────────────┘        │
     ▲ 1                                                                                       │
     └───────────────────────────────────────────────────────────────────────────┐             │
                                                                                  │             │
┌────────────────┐        ┌──────────────────────┐        ┌──────────────────┐   │             │
│ scoring_models │ 1───* ─│  scoring_weights     │───*──1 │signal_definitions│   │             │
└───────┬────────┘        └──────────────────────┘        └────────┬─────────┘   │             │
        │ 1                                                        │ 1            │             │
        │                                                          │              │             │
        ▼ *                                                        ▼ *            │             │
┌──────────────┐  1 ────────────────────────────*  ┌────────────────────────┐     │             │
│ trust_scores │◄─────────────────────────────────│  trust_score_signals    │     │             │
└──────┬───────┘                                   └────────────────────────┘     │             │
       │ 1                                                                         │             │
       │ *                              seller_profiles ◄──────────────────────────┘             │
       ▼                                        ▲                                                │
┌────────────┐ 1─* ┌──────────────────┐         │                                                │
│  appeals   │────►│ appeal_messages  │         └────────────────────────────────────────────────┘
└─────┬──────┘     └──────────────────┘
      │ *                              ┌────────────────┐ 1─* ┌──────────┐ 1─* ┌──────────────────┐
      ▼ 1                              │  api_clients   │────►│ api_keys │────►│ api_request_logs │
┌──────────────┐                       └───────┬────────┘     └──────────┘     └──────────────────┘
│review_cases  │                               │ 1─*
└──────────────┘                               ▼
                                        ┌────────────────────┐ 1─* ┌────────────────────┐
                                        │ webhook_endpoints  │────►│ webhook_deliveries │
                                        └────────────────────┘     └────────────────────┘

Cross-cutting: files · audit_logs · job_runs · outbox_events · notifications
```

## 4. Table catalogue

### 4.1 Identity & access

#### `users`
The single account table for every persona. One table with roles beats separate `buyers`/`sellers`/`admins`
tables: a person can be both a buyer and a seller, and auth logic must not be written three times.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | UUIDv7 |
| email | citext | NOT NULL, partial UQ where `deleted_at IS NULL` | `citext` makes `A@x.com` = `a@x.com` |
| email_verified_at | timestamptz | NULL | Drives the EMAIL signal |
| password_hash | text | NULL | NULL for future OAuth-only accounts |
| full_name | varchar(150) | NOT NULL | |
| status | account_status | NOT NULL DEFAULT 'PENDING' | |
| primary_role | user_role | NOT NULL DEFAULT 'BUYER' | Denormalised for fast routing; `user_roles` is authoritative |
| mfa_enabled | boolean | NOT NULL DEFAULT false | |
| mfa_secret_encrypted | bytea | NULL | Envelope-encrypted |
| failed_login_count | smallint | NOT NULL DEFAULT 0 | Lockout |
| locked_until | timestamptz | NULL | |
| last_login_at | timestamptz | NULL | |
| password_changed_at | timestamptz | NULL | Invalidates older refresh tokens |
| created_at / updated_at / deleted_at | timestamptz | | |
| version | integer | NOT NULL DEFAULT 1 | |

Indexes: `uq_users_email (email) WHERE deleted_at IS NULL`, `ix_users_status`,
`ix_users_created_at`, GIN trigram on `full_name` for admin search.

#### `roles`, `permissions`, `role_permissions`, `user_roles`
Full RBAC rather than a single role column, because the proposal needs at minimum an admin **and** a
reviewer with different powers, and because permissions must be listable in the JWT.

- `roles(id, key user_role UNIQUE, name, description, is_system bool, created_at, updated_at)`
- `permissions(id, key varchar(80) UNIQUE, resource, action, description)` — e.g. `seller:read`,
  `identity:approve`, `scoring_model:activate`, `api_client:create`, `appeal:resolve`
- `role_permissions(role_id, permission_id)` — composite PK
- `user_roles(user_id, role_id, granted_by, granted_at, expires_at NULL)` — composite PK; `expires_at`
  supports temporary elevation without a schema change

#### `refresh_tokens`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK→users ON DELETE CASCADE | |
| token_hash | bytea NOT NULL UNIQUE | SHA-256 of the token; **the raw token is never stored** |
| family_id | uuid NOT NULL | Rotation family — reuse detection revokes the whole family |
| parent_id | uuid NULL FK→refresh_tokens | Rotation chain |
| device_id | uuid NULL FK→devices | "Sign out this device" |
| ip_address | inet NULL | |
| user_agent | text NULL | |
| expires_at | timestamptz NOT NULL | |
| revoked_at | timestamptz NULL | |
| revoked_reason | varchar(50) NULL | `ROTATED`, `LOGOUT`, `REUSE_DETECTED`, `PASSWORD_CHANGE` |

Indexes: `ix_refresh_tokens_user_active (user_id) WHERE revoked_at IS NULL`, `ix_refresh_tokens_family`,
`ix_refresh_tokens_expires_at` (cleanup job).

#### `verification_tokens` (email verification, password reset, email change)
`(id, user_id, purpose token_purpose, token_hash bytea UNIQUE, target citext, expires_at, consumed_at,
created_ip inet, created_at)`. Single-use, hashed, short-lived. One table for three flows because they are
structurally identical — three tables would be three copies of the same expiry/consumption bug surface.

#### `otp_codes` (phone OTP — feature F2)
`(id, user_id, phone_number_id, purpose otp_purpose, code_hash bytea, attempts smallint DEFAULT 0,
max_attempts smallint DEFAULT 5, expires_at, consumed_at, sent_at, delivery_provider, delivery_status,
created_at)`.
The OTP is **hashed** (HMAC-SHA256 with a server pepper) — a database leak must not hand out live codes.
`attempts` and a separate Redis send-throttle defend the two distinct attacks: guessing a code, and using
OTP sends as an SMS-cost/DoS vector.

#### `consents`
`(id, user_id, consent_type, version varchar(20), granted bool, granted_at, revoked_at, ip inet,
user_agent, created_at)`.
Exists specifically because TrustLens processes **biometric data** (a face image and its embedding) and
national ID documents. Explicit, versioned, timestamped consent for `BIOMETRIC_PROCESSING` is both an
ethical baseline and a legal one under most data-protection regimes.

### 4.2 Seller domain

#### `seller_profiles`
Separates seller-specific attributes from account attributes (a buyer row carries none of these columns).

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK→users UNIQUE | 1:1 |
| handle | citext UNIQUE | Public URL slug: `/seller/{handle}` |
| display_name | varchar(150) NOT NULL | |
| business_type | varchar(50) NULL | individual / business |
| marketplace_id | uuid NULL FK→marketplaces | Which platform they sell on |
| external_seller_ref | varchar(120) NULL | Partner's own ID — how a marketplace looks a seller up |
| city / country_code | varchar | Geo-consistency signal vs IP country |
| bio | text NULL | |
| account_opened_at | timestamptz NOT NULL | BEHAVIOUR signal input; may predate TrustLens if supplied by a partner |
| current_trust_score_id | uuid NULL FK→trust_scores | Denormalised pointer to the current score |
| identity_status / phone_status / email_status | verification_status | Denormalised for fast dashboard reads |
| is_flagged | boolean DEFAULT false | Under manual review |
| created_at / updated_at / deleted_at / version | | |

Unique: `uq_seller_external_ref (marketplace_id, external_seller_ref) WHERE deleted_at IS NULL`.
Indexes: `handle`, `current_trust_score_id`, `is_flagged`, GIN trigram on `display_name`.

> **WHY denormalise the four status columns and the score pointer:** the seller dashboard and the public
> page both need "current state" in one round trip. The authoritative data still lives in
> `identity_verifications` / `trust_scores`; these columns are maintained by the same use case that writes
> those tables, inside the same transaction, so they cannot drift.

#### `marketplaces`
`(id, name, slug UNIQUE, website_url, country_code, is_active, created_at, updated_at)` — OLX-style
platform, rental portal, vehicle site, freelance platform. Needed to scope `external_seller_ref` and to
report per-marketplace fraud rates.

### 4.3 Verification signal tables

#### `identity_documents` (F1 — the OCR half)
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| seller_id | uuid FK→seller_profiles | |
| document_type | document_type | CNIC_FRONT / CNIC_BACK / SELFIE |
| file_id | uuid FK→files | The stored image |
| status | verification_status | |
| ocr_engine | varchar(40) | `easyocr` |
| ocr_engine_version | varchar(20) | Reproducibility |
| ocr_confidence | numeric(4,3) | 0.000–1.000 |
| ocr_raw | jsonb | Full token/bbox output — evidence for appeals |
| extracted_name | varchar(150) NULL | |
| extracted_cnic_encrypted | bytea NULL | **AES-256-GCM envelope encrypted** |
| extracted_cnic_hash | bytea NULL | HMAC — enables duplicate-CNIC detection *without* decryption |
| extracted_dob_encrypted | bytea NULL | |
| extracted_expiry | date NULL | Expired CNIC is a FAIL |
| quality_score | numeric(4,3) NULL | Blur/glare/crop gate |
| rejection_reason | varchar(120) NULL | |
| processed_at | timestamptz NULL | |
| created_at / updated_at / deleted_at | | |

Index: `ix_identity_documents_cnic_hash (extracted_cnic_hash)` — **the single most valuable index for
fraud detection in the schema**: it finds one CNIC registered across many seller accounts in O(log n)
while the CNIC number itself stays encrypted at rest.

#### `identity_verifications` (F1 — the face-match half)
`(id, seller_id, front_document_id, back_document_id, selfie_document_id, face_match_engine
'deepface', engine_version, face_similarity numeric(5,4), face_distance numeric(5,4), threshold_used
numeric(5,4), liveness_passed bool NULL, decision verification_status, decision_source
'AUTO'|'MANUAL', decided_by uuid NULL FK→users, decision_reason text, name_match_score numeric(4,3),
raw_result jsonb, verified_at, created_at, updated_at)`.

Storing `threshold_used` alongside `face_similarity` is what makes an old decision explainable after the
threshold is tuned — without it, a past rejection becomes indefensible in an appeal.

#### `phone_numbers` (F2)
`(id, user_id, e164 varchar(20), phone_hash bytea, is_primary bool, verified_at, carrier_name,
line_type 'MOBILE'|'VOIP'|'LANDLINE'|'UNKNOWN', is_disposable bool, country_code, lookup_raw jsonb,
lookup_at, created_at, updated_at, deleted_at)`.
Unique: `(user_id, e164) WHERE deleted_at IS NULL`; plus `ix_phone_numbers_hash` to detect one number
reused across accounts. `line_type = 'VOIP'` is precisely the "throwaway phone number" pattern the
proposal names.

#### `email_addresses` (F3)
`(id, user_id, email citext, email_hash bytea, is_primary bool, verified_at, domain varchar(255),
is_disposable bool, mx_valid bool, domain_age_days integer NULL, lookup_raw jsonb, lookup_at,
created_at, updated_at, deleted_at)`.
A separate table from `users.email` because a seller may add a business email, and because email *checks*
produce their own evidence that must be stored and re-run independently of login credentials.

#### `devices` + `user_devices` (F4)
- `devices(id, fingerprint_hash bytea UNIQUE, user_agent, browser, browser_version, os, os_version,
  device_type, screen_resolution, timezone, languages, is_bot bool, is_emulator bool, first_seen_at,
  last_seen_at, created_at, updated_at)`
- `user_devices(user_id, device_id, first_seen_at, last_seen_at, session_count int, is_trusted bool,
  created_at)` — composite PK

The many-to-many is the whole point: the query
`SELECT device_id FROM user_devices GROUP BY device_id HAVING count(DISTINCT user_id) > 3`
is the "multiple accounts created from one device" detector named in the problem statement.

#### `ip_addresses` + `access_events` (F4 network half)
- `ip_addresses(id, ip inet UNIQUE, ip_version, asn integer, asn_org, country_code, region, city,
  is_vpn bool, is_proxy bool, is_tor bool, is_datacenter bool, abuse_score smallint, provider
  varchar(40), lookup_raw jsonb, looked_up_at, created_at, updated_at)` — one row per distinct IP, so a
  paid reputation lookup happens once, not once per request.
- `access_events(id, user_id NULL, device_id NULL, ip_address_id NULL, event_type 'LOGIN'|'REGISTER'
  |'VERIFY'|'API', occurred_at, request_id, user_agent, created_at)` — append-only, **partitioned monthly
  by `occurred_at`**, 12-month retention. Feeds both the NETWORK signal and the BEHAVIOUR (account
  activity) signal.

### 4.4 Listings (F5)

#### `listings`
`(id, seller_id FK, marketplace_id FK NULL, external_listing_ref varchar(160) NULL, source
listing_source, title varchar(250), description text, price numeric(14,2) NULL, currency char(3),
category varchar(80), condition varchar(40), city, country_code, external_url text NULL, posted_at,
status listing_status, latest_analysis_id uuid NULL FK→listing_analyses, created_at, updated_at,
deleted_at, version)`.
Indexes: `(seller_id, created_at DESC)`, `status`, GIN trigram on `title`,
`uq_listing_external (marketplace_id, external_listing_ref) WHERE deleted_at IS NULL`.

#### `listing_images`
`(id, listing_id FK, file_id FK→files, position smallint, width, height, perceptual_hash bytea NULL,
sha256 bytea, is_primary bool, created_at)`.
`perceptual_hash` is stored **now** even though reverse-image search is future scope — the hash is
computed at upload time and cannot be backfilled once the images are purged. An index on it turns the
future stolen-photo feature into a query rather than a re-ingestion project.

#### `listing_analyses` (the AI evidence)
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| listing_id | uuid FK | |
| analyzer_type | varchar(20) | `LLM` or `CLASSIFIER` — both run, both stored |
| provider | varchar(30) | `openai` / `anthropic` / `internal` |
| model_name | varchar(80) | e.g. `claude-…`, `scamclf-v3` |
| model_version | varchar(40) | |
| prompt_version | varchar(20) NULL | Which prompt template produced this |
| risk_score | numeric(5,2) | 0–100, listing-level |
| confidence | numeric(4,3) | |
| labels | jsonb | `["urgency_pressure","off_platform_contact","price_anomaly"]` |
| findings | jsonb | Per-label evidence + quoted spans |
| price_deviation_pct | numeric(6,2) NULL | vs category median |
| raw_response | jsonb | Redacted provider payload |
| input_tokens / output_tokens | integer | Cost tracking |
| latency_ms | integer | |
| cost_usd | numeric(10,6) | |
| analysed_at | timestamptz | |
| created_at | timestamptz | |

Append-only — analyses are never updated. Re-analysing writes a new row and repoints
`listings.latest_analysis_id`, so the history of "what the AI said and when" survives model upgrades.

### 4.5 Scoring (F6) — the core of the system

#### `signal_definitions`
The catalogue of scoreable signals. Rows, not code, so a new signal is a migration + seed, not a refactor.

`(id, code varchar(60) UNIQUE, category signal_category, name, description, buyer_facing_description,
max_points smallint, is_active bool, is_critical bool, display_order smallint, created_at, updated_at)`

Seed (v1):

| code | category | max_points | critical |
|---|---|---|---|
| `IDENTITY_DOCUMENT_VALID` | IDENTITY | 15 | ✔ |
| `IDENTITY_FACE_MATCH` | IDENTITY | 15 | ✔ |
| `PHONE_VERIFIED` | PHONE | 10 | |
| `PHONE_NOT_DISPOSABLE` | PHONE | 5 | |
| `EMAIL_VERIFIED` | EMAIL | 6 | |
| `EMAIL_NOT_DISPOSABLE` | EMAIL | 4 | |
| `DEVICE_NOT_SHARED` | DEVICE | 6 | |
| `DEVICE_CONSISTENT` | DEVICE | 4 | |
| `NETWORK_NOT_VPN` | NETWORK | 6 | |
| `NETWORK_GEO_CONSISTENT` | NETWORK | 4 | |
| `ACCOUNT_AGE` | BEHAVIOUR | 6 | |
| `ACTIVITY_CONSISTENT` | BEHAVIOUR | 4 | |
| `LISTING_CONTENT_SAFE` | LISTING | 10 | |
| `LISTING_PRICE_REALISTIC` | LISTING | 5 | |

`is_critical` marks signals that trigger a **hard cap** on failure (see [08](08-trust-score-engine.md)).

#### `scoring_models`
`(id, version varchar(20) UNIQUE, name, description, is_active bool, algorithm varchar(30)
DEFAULT 'WEIGHTED_SUM', config jsonb, activated_at, activated_by FK→users, created_at, updated_at)`.
Partial unique index guarantees **at most one active model**:
`CREATE UNIQUE INDEX uq_scoring_models_active ON scoring_models ((is_active)) WHERE is_active;`

#### `scoring_weights`
`(id, scoring_model_id FK, signal_definition_id FK, weight numeric(6,3), threshold_config jsonb,
hard_cap_on_fail smallint NULL, is_enabled bool, created_at, updated_at)`,
unique `(scoring_model_id, signal_definition_id)`, check `weight >= 0`.
A DB-level check plus an application invariant enforce that enabled weights sum to 100 for the active model.

> **WHY weights in the database:** the FYP demo will need weight tuning during evaluation, and a
> supervisor may challenge a specific weighting. Tuning through the admin UI, with the old model version
> preserved and every historical score still pointing at the model that produced it, turns "we changed the
> weights" from a data-integrity problem into an audit-log entry.

#### `trust_scores`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| seller_id | uuid FK→seller_profiles | |
| scoring_model_id | uuid FK→scoring_models | Which rules produced this |
| score | smallint NOT NULL | `CHECK (score BETWEEN 0 AND 100)` |
| risk_level | risk_level NOT NULL | Derived, stored for indexed filtering |
| raw_score | numeric(6,3) | Pre-rounding, pre-cap |
| available_weight | numeric(6,3) | Sum of weights actually evaluated (unavailable signals excluded) |
| cap_applied | smallint NULL | Which hard cap, if any, clamped the score |
| confidence | numeric(4,3) | Aggregate evidence confidence |
| trigger | score_trigger NOT NULL | Why it recomputed |
| is_current | boolean NOT NULL DEFAULT true | |
| is_manual_override | boolean DEFAULT false | |
| override_reason | text NULL | **Required** when `is_manual_override` (CHECK constraint) |
| overridden_by | uuid NULL FK→users | |
| computed_at | timestamptz NOT NULL | |
| valid_until | timestamptz NOT NULL | A14: +30 days |
| created_at | timestamptz | |

Constraints: `CREATE UNIQUE INDEX uq_trust_scores_current ON trust_scores (seller_id) WHERE is_current;`
— a seller can have **exactly one** current score, enforced by the database rather than by hope.
`CHECK (NOT is_manual_override OR override_reason IS NOT NULL)`.
Indexes: `(seller_id, computed_at DESC)` for history, `(risk_level) WHERE is_current` for admin filters.

**Immutable and append-only.** Recomputation inserts a new row and flips the old `is_current` to false in
the same transaction. This gives score history (a "future scope" item) for free and makes every past
score defensible.

#### `trust_score_signals` — **the explainability table**
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| trust_score_id | uuid FK ON DELETE CASCADE | |
| signal_definition_id | uuid FK | |
| signal_code | varchar(60) | Denormalised so an old row survives a definition rename |
| category | signal_category | |
| status | signal_status | PASS / PARTIAL / FAIL / UNAVAILABLE / NOT_APPLICABLE |
| weight | numeric(6,3) | Weight at computation time |
| points_awarded | numeric(6,3) | Actual contribution |
| points_possible | numeric(6,3) | |
| confidence | numeric(4,3) | |
| reason_code | varchar(60) | Machine-readable, e.g. `PHONE_LINE_TYPE_VOIP` |
| reason_text | text | Buyer-readable, e.g. "Phone number is an internet number, not a mobile SIM" |
| evidence | jsonb | Non-PII supporting values (`{"line_type":"VOIP","checked_at":"…"}`) |
| source_table / source_id | varchar / uuid | Pointer back to the raw record |
| created_at | timestamptz | |

Unique `(trust_score_id, signal_definition_id)`.

This single table is what makes the score *explainable* rather than a number: for every score, every
signal's status, weight, contribution, machine reason code, human sentence, and a pointer to the
underlying evidence — frozen at computation time. It answers "why is this seller high risk?" without
recomputing anything and without consulting an LLM.

### 4.6 Appeals & moderation (F7)

- **`appeals`** — `(id, seller_id FK, trust_score_id FK, submitted_by FK→users, reason_category
  varchar(50), reason text, status appeal_status, assigned_to uuid NULL FK→users, assigned_at,
  resolution_note text NULL, decision varchar(20) NULL, resulting_score_id uuid NULL FK→trust_scores,
  submitted_at, resolved_at, resolved_by, created_at, updated_at, deleted_at, version)`.
  It references the *specific* `trust_score_id` under appeal — appealing "my score" is meaningless once the
  score changes; appealing *that computation* is precise and reviewable.
  Rate limit (appeal policy): max 1 open appeal per seller, max 3 per 30 days.
- **`appeal_messages`** — `(id, appeal_id FK, sender_id FK→users, sender_role user_role, body text,
  attachments jsonb, is_internal bool, created_at)`. `is_internal` keeps reviewer notes out of the
  seller's view without a second table.
- **`review_cases`** — the admin work queue: `(id, seller_id FK, case_type 'IDENTITY_REVIEW'|
  'FRAUD_FLAG'|'APPEAL'|'DEVICE_CLUSTER', priority smallint, status review_status, assigned_to,
  assigned_at, trigger_reason varchar(120), related_entity_type, related_entity_id, decision
  varchar(20) NULL, decision_note text, resolved_at, resolved_by, created_at, updated_at)`.
  Separate from `appeals` because most review work is **system-initiated** (a device cluster tripped a
  rule), not seller-initiated. Merging them would force every automatic flag to masquerade as an appeal.

### 4.7 Public API (F8)

- **`api_clients`** — `(id, name, slug UNIQUE, marketplace_id FK NULL, contact_email, contact_name,
  status 'PENDING'|'ACTIVE'|'SUSPENDED', rate_limit_tier varchar(20), monthly_quota integer,
  allowed_origins text[], allowed_ips inet[] NULL, webhook_secret_encrypted bytea NULL, created_by,
  created_at, updated_at, deleted_at)`.
- **`api_keys`** — `(id, api_client_id FK, name, key_prefix varchar(16) UNIQUE, key_hash bytea UNIQUE,
  scopes text[], status api_key_status, last_used_at, last_used_ip inet, expires_at, revoked_at,
  revoked_by, created_by, created_at, updated_at, deleted_at)`.
  The raw key is shown **once** at creation and never stored. `key_prefix` (e.g. `tl_live_a1b2c3`) makes
  lookup an indexed equality match, then a constant-time compare of the argon2 hash — you cannot look up
  by hash alone without hashing every candidate.
- **`api_request_logs`** — `(id, api_key_id FK NULL, api_client_id FK NULL, method, path, status_code,
  latency_ms, ip inet, user_agent, request_id, seller_id NULL, error_code NULL, occurred_at)`.
  Append-only, **partitioned monthly**, 90-day retention. Powers quota reporting, abuse detection, and
  partner-facing usage stats.
- **`webhook_endpoints`** / **`webhook_deliveries`** — outbound score-change notifications
  (`SCORE_UPDATED` etc.) with HMAC signature, `attempt_count`, `next_retry_at`, `response_status`,
  `delivery_status`. Scoped for phase 2 but modelled now because retro-fitting reliable delivery is
  painful.

### 4.8 Cross-cutting

- **`files`** — `(id, owner_user_id FK NULL, purpose file_purpose, storage_provider, bucket,
  object_key UNIQUE, original_filename, mime_type, size_bytes, sha256 bytea, width, height,
  scan_status scan_status, is_encrypted bool, expires_at NULL, deleted_at NULL, created_at, updated_at)`.
  Every binary in one table so the retention job (`purge_expired_media`) has exactly one place to look —
  a hard requirement given CNIC images have a 90-day retention rule.
- **`audit_logs`** — `(id, actor_id NULL, actor_type 'USER'|'SYSTEM'|'API_CLIENT', action varchar(80),
  entity_type varchar(60), entity_id uuid NULL, before jsonb NULL, after jsonb NULL, ip inet,
  user_agent, request_id, occurred_at)`. Append-only, no updates, no deletes, monthly partitions.
  Written by the `AuditingUnitOfWork` decorator on every state-changing use case, so coverage doesn't
  depend on a developer remembering.
- **`job_runs`** — `(id, job_name, job_key varchar(120) NULL, status job_status, related_entity_type,
  related_entity_id, attempt smallint, max_attempts smallint, payload jsonb, result jsonb NULL,
  error_message text NULL, error_type varchar(80) NULL, request_id, queued_at, started_at, finished_at,
  duration_ms)`. Mirrors ARQ state into Postgres so the frontend can poll `GET /api/v1/jobs/{id}` and the
  admin panel can show dead-lettered work. Redis alone would lose this on eviction.
- **`outbox_events`** — `(id, aggregate_type, aggregate_id, event_type, payload jsonb, occurred_at,
  published_at NULL, attempts smallint, created_at)`. Transactional outbox: domain events are written in
  the **same transaction** as the state change and published by a poller. Without it, "score updated but
  webhook never sent" (or the reverse) is inevitable.
- **`notifications`** — `(id, user_id FK, type varchar(50), title, body, data jsonb, channel
  'IN_APP'|'EMAIL'|'SMS', read_at NULL, sent_at NULL, created_at)`.

## 5. Index summary (beyond PK/FK)

| Table | Index | Serves |
|---|---|---|
| users | `uq (email) WHERE deleted_at IS NULL` | Login, re-registration after deletion |
| users | GIN trgm `full_name` | Admin search |
| refresh_tokens | `(user_id) WHERE revoked_at IS NULL`; `(family_id)`; `(expires_at)` | Auth + reuse detection + cleanup |
| seller_profiles | `uq(handle)`; `(is_flagged)`; GIN trgm `display_name`; `uq(marketplace_id, external_seller_ref)` | Public page, queue, API lookup |
| identity_documents | `(extracted_cnic_hash)`; `(seller_id, document_type)` | **Duplicate-CNIC fraud detection** |
| phone_numbers | `(phone_hash)`; `uq(user_id, e164)` | Reused-number detection |
| email_addresses | `(email_hash)`; `(domain)` | Reused-email and disposable-domain analysis |
| user_devices | `(device_id)`; `(user_id)` | Multi-account-per-device clustering |
| ip_addresses | `uq(ip)`; `(is_vpn) WHERE is_vpn` | Network signal |
| access_events | `(user_id, occurred_at DESC)`; monthly partitions | Behaviour signal, forensics |
| listings | `(seller_id, created_at DESC)`; `(status)`; GIN trgm `title` | Dashboard, moderation |
| listing_analyses | `(listing_id, analysed_at DESC)` | Latest analysis |
| listing_images | `(perceptual_hash)` | Future stolen-photo detection |
| trust_scores | `uq(seller_id) WHERE is_current`; `(seller_id, computed_at DESC)`; `(risk_level) WHERE is_current` | Score reads, history, admin filters |
| trust_score_signals | `(trust_score_id)`; `uq(trust_score_id, signal_definition_id)` | Breakdown fetch |
| appeals | `(status, submitted_at)`; `(assigned_to) WHERE status IN ('OPEN','UNDER_REVIEW')` | Appeal queue |
| review_cases | `(status, priority DESC, created_at)` | Work queue ordering |
| api_keys | `uq(key_prefix)`; `(api_client_id) WHERE status='ACTIVE'` | Constant-work key auth |
| api_request_logs | `(api_key_id, occurred_at DESC)`; monthly partitions | Quota, abuse |
| audit_logs | `(entity_type, entity_id, occurred_at DESC)`; `(actor_id)`; monthly partitions | Investigations |
| outbox_events | `(published_at) WHERE published_at IS NULL` | Outbox poller |
| job_runs | `(status, queued_at)`; `(related_entity_type, related_entity_id)` | Job polling, dead letters |

## 6. Partitioning

`access_events`, `api_request_logs`, and `audit_logs` are `PARTITION BY RANGE (occurred_at)`, monthly,
created a month ahead by a cron job. They are the only tables whose growth is unbounded by user count.
Retention becomes `DROP PARTITION` — instant — instead of a `DELETE` that bloats the table and holds locks.

## 7. Transactions & concurrency

| Situation | Handling |
|---|---|
| Score recomputation | Per-seller Redis lock + queue dedup key; `is_current` flip and new insert in one transaction |
| Concurrent admin edits | `version` column, optimistic locking → 409 with the current value |
| Refresh-token rotation | `SELECT … FOR UPDATE` on the token row; reuse of a rotated token revokes the whole family |
| OTP verification | Atomic `UPDATE … SET attempts = attempts + 1 WHERE id = … AND attempts < max_attempts RETURNING *` |
| Quota counting | Redis `INCR` (fast path) reconciled against `api_request_logs` (source of truth) |
| Isolation level | `READ COMMITTED` default; `REPEATABLE READ` for the scoring transaction so the signal set can't shift mid-computation |

## 8. Migrations & seeds

- Alembic, **one head**, in `database/migrations/versions/`, named
  `YYYYMMDDHHMM_<slug>.py`. Autogenerate then hand-review — Alembic reliably misses enum value changes,
  index predicate changes, and check constraints.
- Every migration must be **backward compatible for one release** (expand → migrate → contract), so a
  deploy can roll back without a data restore.
- Data migrations live in separate revisions from schema migrations, so a slow backfill can be rerun or
  skipped without blocking a schema change.
- Seeds in `database/seeds/` are **idempotent upserts**: `roles`, `permissions`, `role_permissions`,
  `signal_definitions`, `scoring_models v1` + `scoring_weights`, `marketplaces`, plus a dev-only
  `demo_data` seed (sellers spanning all three risk bands, for the demo and for E2E tests).
