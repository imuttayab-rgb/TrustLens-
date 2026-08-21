# 12 — Environment Variables

## 1. Rules

1. **Never commit `.env`.** Only `.env.example`, with placeholder values and a comment per variable.
2. **Fail fast.** Each app validates its full environment at startup via `pydantic-settings` / a Zod
   schema and refuses to boot on a missing or malformed value. No `os.getenv(...) or "default-secret"`.
3. **No defaults for secrets.** A default `JWT_SECRET` is how a dev key reaches production.
4. **Prefix by domain** (`DB_`, `REDIS_`, `AI_`, `STORAGE_`, `SECURITY_`) so settings groups map 1:1 to
   config classes.
5. **`NEXT_PUBLIC_*` is public.** Anything with that prefix is compiled into the browser bundle. Never
   put a secret behind it — this is the single most common env-var security mistake in Next.js projects.
6. **Same variable names in every environment**; only values differ.
7. Secrets are provisioned in the platform (Railway/Vercel dashboards, GitHub Actions secrets), never in
   the repository.

## 2. Core

| Variable       | Example                 | Required | Description                                                                      |
| -------------- | ----------------------- | :------: | -------------------------------------------------------------------------------- |
| `ENV`          | `development`           |    ✔     | `development` \| `test` \| `staging` \| `production`. Drives every other default |
| `DEBUG`        | `true`                  |    ✔     | Verbose errors, `/docs` exposed. **Asserted `false` in production**              |
| `APP_NAME`     | `TrustLens`             |          | Branding, log field                                                              |
| `APP_VERSION`  | `1.0.0`                 |          | Injected from the git SHA in CI                                                  |
| `API_BASE_URL` | `http://localhost:8000` |    ✔     | Absolute API URL, used in emails and webhooks                                    |
| `WEB_BASE_URL` | `http://localhost:3000` |    ✔     | Used to build verification/reset links                                           |
| `LOG_LEVEL`    | `DEBUG`                 |    ✔     | `DEBUG`/`INFO`/`WARNING`/`ERROR`                                                 |
| `LOG_FORMAT`   | `console`               |          | `console` (dev) \| `json` (deployed)                                             |
| `TZ`           | `UTC`                   |    ✔     | Always UTC; formatting is a frontend concern                                     |

## 3. Database

| Variable                  | Example                                                             | Required | Description                                               |
| ------------------------- | ------------------------------------------------------------------- | :------: | --------------------------------------------------------- |
| `DATABASE_URL`            | `postgresql+asyncpg://trustlens:trustlens@localhost:5432/trustlens` |    ✔     | Async DSN for the app                                     |
| `DATABASE_URL_SYNC`       | `postgresql+psycopg://…`                                            |    ✔     | Sync DSN — Alembic requires it                            |
| `DB_POOL_SIZE`            | `10`                                                                |          | Per-process pool size                                     |
| `DB_MAX_OVERFLOW`         | `5`                                                                 |          | Burst connections above the pool                          |
| `DB_POOL_TIMEOUT`         | `30`                                                                |          | Seconds to wait for a connection                          |
| `DB_POOL_RECYCLE`         | `1800`                                                              |          | Recycle connections before the provider's idle timeout    |
| `DB_ECHO`                 | `false`                                                             |          | Log every SQL statement — dev only                        |
| `DB_STATEMENT_TIMEOUT_MS` | `10000`                                                             |          | Server-side statement timeout; caps runaway admin queries |
| `DB_SSL_REQUIRE`          | `false`                                                             |          | **Must be `true` in production**                          |

Pool sizing matters on Railway: `DB_POOL_SIZE × replicas × (api + worker)` must stay under the Postgres
`max_connections`. With two API replicas and one worker at pool 10, that is ~30 connections plus overflow.

## 4. Redis

| Variable                    | Example                    | Required | Description                                                                                     |
| --------------------------- | -------------------------- | :------: | ----------------------------------------------------------------------------------------------- |
| `REDIS_URL`                 | `redis://localhost:6379/0` |    ✔     | Cache + rate limiting                                                                           |
| `REDIS_QUEUE_URL`           | `redis://localhost:6379/1` |    ✔     | ARQ job queue — **a separate DB index**, so a `FLUSHDB` of the cache never destroys queued jobs |
| `REDIS_MAX_CONNECTIONS`     | `20`                       |          |                                                                                                 |
| `CACHE_TTL_SCORE_SECONDS`   | `300`                      |          | Public score cache TTL                                                                          |
| `CACHE_TTL_DEFAULT_SECONDS` | `120`                      |          |                                                                                                 |

## 5. Security & auth

| Variable                            | Example                       | Required | Description                                                                                                           |
| ----------------------------------- | ----------------------------- | :------: | --------------------------------------------------------------------------------------------------------------------- |
| `SECURITY_JWT_PRIVATE_KEY`          | PEM (base64)                  |    ✔     | Ed25519 signing key. Generate: `openssl genpkey -algorithm ed25519`                                                   |
| `SECURITY_JWT_PUBLIC_KEY`           | PEM (base64)                  |    ✔     | Verification key                                                                                                      |
| `SECURITY_JWT_ALGORITHM`            | `EdDSA`                       |          |                                                                                                                       |
| `SECURITY_JWT_ISSUER`               | `https://api.trustlens.app`   |    ✔     |                                                                                                                       |
| `SECURITY_JWT_AUDIENCE`             | `trustlens-web`               |    ✔     |                                                                                                                       |
| `SECURITY_ACCESS_TOKEN_TTL_MINUTES` | `15`                          |    ✔     |                                                                                                                       |
| `SECURITY_REFRESH_TOKEN_TTL_DAYS`   | `30`                          |    ✔     |                                                                                                                       |
| `SECURITY_REFRESH_IDLE_TTL_DAYS`    | `7`                           |          | Idle expiry independent of absolute expiry                                                                            |
| `SECURITY_PASSWORD_MIN_LENGTH`      | `12`                          |          |                                                                                                                       |
| `SECURITY_ARGON2_MEMORY_KIB`        | `65536`                       |          | Raise as hardware improves                                                                                            |
| `SECURITY_ARGON2_TIME_COST`         | `3`                           |          |                                                                                                                       |
| `SECURITY_ARGON2_PARALLELISM`       | `4`                           |          |                                                                                                                       |
| `SECURITY_OTP_PEPPER`               | 32-byte random                |    ✔     | HMAC pepper for OTP hashing — **not** in the DB, so a DB leak doesn't yield live codes                                |
| `SECURITY_TOKEN_PEPPER`             | 32-byte random                |    ✔     | Pepper for verification/refresh token hashes                                                                          |
| `SECURITY_ENCRYPTION_KEY`           | 32-byte base64                |    ✔     | AES-256-GCM master key for CNIC/DOB/MFA-secret envelope encryption                                                    |
| `SECURITY_ENCRYPTION_KEY_ID`        | `k1`                          |    ✔     | Key identifier stored alongside ciphertext to enable rotation                                                         |
| `SECURITY_API_KEY_PREFIX`           | `tl_live`                     |          | `tl_test` in non-production                                                                                           |
| `SECURITY_CORS_ORIGINS`             | `http://localhost:3000`       |    ✔     | Comma-separated allowlist. **Never `*` in production**                                                                |
| `SECURITY_TRUSTED_HOSTS`            | `localhost,api.trustlens.app` |    ✔     | Host-header allowlist                                                                                                 |
| `SECURITY_TRUSTED_PROXY_COUNT`      | `1`                           |    ✔     | How many proxy hops to trust in `X-Forwarded-For`. Wrong value ⇒ rate limiting and IP signals are trivially spoofable |
| `SECURITY_MFA_REQUIRED_ROLES`       | `ADMIN,REVIEWER`              |          |                                                                                                                       |

## 6. AI providers

| Variable                     | Example      | Required | Description                                                                      |
| ---------------------------- | ------------ | :------: | -------------------------------------------------------------------------------- |
| `AI_PROVIDER`                | `anthropic`  |    ✔     | `openai` \| `anthropic` — selects the `LlmAnalyzer` adapter                      |
| `AI_OPENAI_API_KEY`          | `sk-…`       |  cond.   | Required when `AI_PROVIDER=openai`                                               |
| `AI_OPENAI_MODEL`            | `gpt-…`      |  cond.   |                                                                                  |
| `AI_ANTHROPIC_API_KEY`       | `sk-ant-…`   |  cond.   | Required when `AI_PROVIDER=anthropic`                                            |
| `AI_ANTHROPIC_MODEL`         | `claude-…`   |  cond.   |                                                                                  |
| `AI_REQUEST_TIMEOUT_SECONDS` | `30`         |          |                                                                                  |
| `AI_MAX_RETRIES`             | `3`          |          | Exponential backoff with jitter                                                  |
| `AI_MAX_OUTPUT_TOKENS`       | `2048`       |          |                                                                                  |
| `AI_MONTHLY_BUDGET_USD`      | `50`         |          | Soft cap; analysis degrades to classifier-only when exceeded                     |
| `AI_PROMPT_VERSION`          | `v1`         |          | Recorded on every `listing_analyses` row                                         |
| `OCR_ENGINE`                 | `easyocr`    |    ✔     |                                                                                  |
| `OCR_LANGUAGES`              | `en,ur`      |          | EasyOCR language packs for CNIC text                                             |
| `OCR_MIN_CONFIDENCE`         | `0.60`       |          | Below this → manual review                                                       |
| `OCR_GPU`                    | `false`      |          |                                                                                  |
| `FACE_MATCH_MODEL`           | `ArcFace`    |          | DeepFace backbone                                                                |
| `FACE_DETECTOR_BACKEND`      | `retinaface` |          |                                                                                  |
| `FACE_MATCH_THRESHOLD`       | `0.70`       |    ✔     | Similarity ≥ threshold ⇒ PASS                                                    |
| `FACE_MATCH_REVIEW_LOWER`    | `0.55`       |    ✔     | 0.55–0.70 ⇒ **manual review**, not auto-fail ([08 §9](08-trust-score-engine.md)) |
| `CLASSIFIER_MODEL_VERSION`   | `scamclf-v1` |    ✔     | Artifact version pulled from the registry                                        |
| `CLASSIFIER_THRESHOLD`       | `0.65`       |          |                                                                                  |
| `USE_FAKE_AI`                | `false`      |          | **`true` runs the whole pipeline with fakes — no keys, no internet (NFR-8)**     |

## 7. Object storage

| Variable                        | Example                           | Required | Description                                                   |
| ------------------------------- | --------------------------------- | :------: | ------------------------------------------------------------- |
| `STORAGE_PROVIDER`              | `s3`                              |    ✔     | `s3` \| `local`                                               |
| `STORAGE_ENDPOINT_URL`          | `http://localhost:9002`           |  cond.   | MinIO/R2 endpoint; omit for AWS                               |
| `STORAGE_REGION`                | `auto`                            |          |                                                               |
| `STORAGE_ACCESS_KEY_ID`         | `minioadmin`                      |    ✔     |                                                               |
| `STORAGE_SECRET_ACCESS_KEY`     | `minioadmin`                      |    ✔     |                                                               |
| `STORAGE_BUCKET_DOCUMENTS`      | `trustlens-documents`             |    ✔     | CNIC + selfies — **private, never public**                    |
| `STORAGE_BUCKET_LISTINGS`       | `trustlens-listings`              |    ✔     | Listing images                                                |
| `STORAGE_BUCKET_MODELS`         | `trustlens-models`                |    ✔     | Classifier artifacts                                          |
| `STORAGE_PRESIGN_TTL_SECONDS`   | `300`                             |          | Presigned URL lifetime                                        |
| `STORAGE_MAX_UPLOAD_BYTES`      | `10485760`                        |    ✔     | 10 MB                                                         |
| `STORAGE_ALLOWED_MIME`          | `image/jpeg,image/png,image/webp` |    ✔     | Verified by magic bytes, not by header                        |
| `MEDIA_RETENTION_DAYS_IDENTITY` | `90`                              |    ✔     | Purge window for CNIC/selfie images after a terminal decision |

## 8. Communications

| Variable                                                          | Example                  | Required | Description                     |
| ----------------------------------------------------------------- | ------------------------ | :------: | ------------------------------- |
| `EMAIL_PROVIDER`                                                  | `smtp`                   |    ✔     | `smtp` \| `resend` \| `console` |
| `EMAIL_FROM`                                                      | `no-reply@trustlens.app` |    ✔     |                                 |
| `EMAIL_FROM_NAME`                                                 | `TrustLens`              |          |                                 |
| `SMTP_HOST` / `SMTP_PORT`                                         | `localhost` / `1025`     |  cond.   | MailHog in dev                  |
| `SMTP_USER` / `SMTP_PASSWORD`                                     |                          |  cond.   |                                 |
| `RESEND_API_KEY`                                                  | `re_…`                   |  cond.   |                                 |
| `SMS_PROVIDER`                                                    | `console`                |    ✔     | `twilio` \| `console`           |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` |                          |  cond.   |                                 |
| `OTP_LENGTH`                                                      | `6`                      |          |                                 |
| `OTP_TTL_SECONDS`                                                 | `300`                    |          |                                 |
| `OTP_MAX_ATTEMPTS`                                                | `5`                      |          | Per code                        |
| `OTP_SEND_LIMIT_HOUR` / `OTP_SEND_LIMIT_DAY`                      | `3` / `10`               |          | Caps the SMS-cost abuse vector  |

## 9. Signal-enrichment providers

| Variable                     | Example   | Required | Description                                               |
| ---------------------------- | --------- | :------: | --------------------------------------------------------- |
| `IP_INTEL_PROVIDER`          | `offline` |    ✔     | `ipqualityscore` \| `ipapi` \| `offline`                  |
| `IP_INTEL_API_KEY`           |           |  cond.   |                                                           |
| `IP_INTEL_TIMEOUT_SECONDS`   | `5`       |          |                                                           |
| `IP_INTEL_CACHE_TTL_SECONDS` | `86400`   |          | Protects a limited quota                                  |
| `DISPOSABLE_EMAIL_LIST_URL`  |           |          | Refreshed daily; a bundled snapshot is the fallback       |
| `PHONE_LOOKUP_PROVIDER`      | `none`    |          | `twilio_lookup` \| `none` — drives `PHONE_NOT_DISPOSABLE` |

## 10. Queue & jobs

| Variable                           | Example | Description                                        |
| ---------------------------------- | ------- | -------------------------------------------------- |
| `WORKER_CONCURRENCY`               | `4`     | Concurrent jobs per worker process                 |
| `WORKER_MAX_JOBS`                  | `100`   | Restart after N jobs — bounds ML memory leaks      |
| `JOB_DEFAULT_TIMEOUT_SECONDS`      | `120`   |                                                    |
| `JOB_IDENTITY_TIMEOUT_SECONDS`     | `300`   | OCR + face match need longer                       |
| `JOB_MAX_TRIES`                    | `3`     |                                                    |
| `SCORE_RECOMPUTE_DEBOUNCE_SECONDS` | `10`    | Collapses verification bursts into one computation |
| `SCORE_VALIDITY_DAYS`              | `30`    | Assumption A14                                     |
| `SCORE_MIN_EVIDENCE_WEIGHT`        | `40`    | Below this ⇒ `UNKNOWN`, not `HIGH`                 |

## 11. Rate limiting

| Variable                                   | Example  | Description                                                      |
| ------------------------------------------ | -------- | ---------------------------------------------------------------- |
| `RATE_LIMIT_ENABLED`                       | `true`   |                                                                  |
| `RATE_LIMIT_ANON_PER_MINUTE`               | `60`     |                                                                  |
| `RATE_LIMIT_USER_PER_MINUTE`               | `300`    |                                                                  |
| `RATE_LIMIT_LOGIN_PER_15MIN`               | `5`      |                                                                  |
| `RATE_LIMIT_PUBLIC_API_FREE_PER_MINUTE`    | `60`     |                                                                  |
| `RATE_LIMIT_PUBLIC_API_PARTNER_PER_MINUTE` | `600`    |                                                                  |
| `RATE_LIMIT_FAIL_MODE`                     | `closed` | `closed` for the public API, `open` for auth, when Redis is down |

## 12. Observability

| Variable                      | Example         | Description                       |
| ----------------------------- | --------------- | --------------------------------- |
| `SENTRY_DSN`                  |                 | Error tracking; omit to disable   |
| `SENTRY_TRACES_SAMPLE_RATE`   | `0.1`           |                                   |
| `OTEL_EXPORTER_OTLP_ENDPOINT` |                 | Tracing; omit to disable          |
| `OTEL_SERVICE_NAME`           | `trustlens-api` | Per app                           |
| `METRICS_ENABLED`             | `true`          | Exposes `/metrics`                |
| `METRICS_AUTH_TOKEN`          |                 | Protects `/metrics` in production |

## 13. Frontend (`apps/web`)

| Variable                       | Example                 | Required | Public? | Description                                    |
| ------------------------------ | ----------------------- | :------: | :-----: | ---------------------------------------------- |
| `NEXT_PUBLIC_API_BASE_URL`     | `http://localhost:8000` |    ✔     | **Yes** | Browser → API                                  |
| `API_BASE_URL_INTERNAL`        | `http://api:8000`       |          |   No    | Server components → API (container network)    |
| `NEXT_PUBLIC_APP_URL`          | `http://localhost:3000` |    ✔     | **Yes** | Canonical URLs, OG tags                        |
| `NEXT_PUBLIC_ENV`              | `development`           |    ✔     | **Yes** | Environment banner                             |
| `NEXT_PUBLIC_SENTRY_DSN`       |                         |          | **Yes** | Client error tracking                          |
| `NEXT_PUBLIC_ENABLE_ANALYTICS` | `false`                 |          | **Yes** |                                                |
| `SESSION_COOKIE_NAME`          | `tl_rt`                 |          |   No    |                                                |
| `SESSION_COOKIE_DOMAIN`        | `localhost`             |          |   No    |                                                |
| `REVALIDATE_SECRET`            | random                  |          |   No    | Authenticates on-demand ISR revalidation calls |

Anything holding a credential — an API key, the revalidation secret, the internal API URL — **must not**
carry the `NEXT_PUBLIC_` prefix. A lint rule and a CI check scan for suspicious `NEXT_PUBLIC_*` names
(`*_KEY`, `*_SECRET`, `*_TOKEN`, `*_PASSWORD`) and fail the build.

## 14. Per-environment differences

| Variable                          | development         | test                        | staging                    | production                   |
| --------------------------------- | ------------------- | --------------------------- | -------------------------- | ---------------------------- |
| `ENV`                             | `development`       | `test`                      | `staging`                  | `production`                 |
| `DEBUG`                           | `true`              | `true`                      | `false`                    | `false`                      |
| `LOG_LEVEL` / `LOG_FORMAT`        | `DEBUG` / `console` | `WARNING` / `console`       | `INFO` / `json`            | `INFO` / `json`              |
| Database                          | local Docker        | **ephemeral testcontainer** | managed, separate instance | managed + PITR backups       |
| `DB_SSL_REQUIRE`                  | `false`             | `false`                     | `true`                     | `true`                       |
| `USE_FAKE_AI`                     | optional            | **`true`**                  | `false`                    | `false`                      |
| `SECURITY_API_KEY_PREFIX`         | `tl_test`           | `tl_test`                   | `tl_test`                  | `tl_live`                    |
| `EMAIL_PROVIDER` / `SMS_PROVIDER` | MailHog / console   | console / console           | real (restricted)          | real                         |
| `STORAGE_PROVIDER`                | MinIO               | MinIO                       | S3-compatible              | S3-compatible                |
| `SECURITY_CORS_ORIGINS`           | `localhost:3000`    | `localhost:3000`            | staging domain             | production domain only       |
| `RATE_LIMIT_ENABLED`              | `false`             | `false`                     | `true`                     | `true`                       |
| Swagger `/docs`                   | on                  | on                          | on (auth-gated)            | **off** for the internal API |
| `SENTRY_DSN`                      | unset               | unset                       | set                        | set                          |

Test config never touches a real provider, a real database, or a real key — a test suite that can reach
production infrastructure is a production incident waiting for a bad `.env`.

## 15. `.env.example` (abridged)

```bash
# ── Core ─────────────────────────────────────────────────────────────
ENV=development
DEBUG=true
APP_NAME=TrustLens
API_BASE_URL=http://localhost:8000
WEB_BASE_URL=http://localhost:3000
LOG_LEVEL=DEBUG
LOG_FORMAT=console
TZ=UTC

# ── Database ─────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://trustlens:trustlens@localhost:5432/trustlens
DATABASE_URL_SYNC=postgresql+psycopg://trustlens:trustlens@localhost:5432/trustlens
DB_POOL_SIZE=10
DB_SSL_REQUIRE=false

# ── Redis ────────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
REDIS_QUEUE_URL=redis://localhost:6379/1

# ── Security (generate real values — do NOT use these) ───────────────
# openssl genpkey -algorithm ed25519 -out jwt.pem && base64 -w0 jwt.pem
SECURITY_JWT_PRIVATE_KEY=CHANGEME_BASE64_ED25519_PRIVATE_KEY
SECURITY_JWT_PUBLIC_KEY=CHANGEME_BASE64_ED25519_PUBLIC_KEY
SECURITY_JWT_ISSUER=http://localhost:8000
SECURITY_JWT_AUDIENCE=trustlens-web
SECURITY_ACCESS_TOKEN_TTL_MINUTES=15
SECURITY_REFRESH_TOKEN_TTL_DAYS=30
# openssl rand -base64 32
SECURITY_OTP_PEPPER=CHANGEME_32_BYTE_RANDOM
SECURITY_TOKEN_PEPPER=CHANGEME_32_BYTE_RANDOM
SECURITY_ENCRYPTION_KEY=CHANGEME_32_BYTE_BASE64
SECURITY_ENCRYPTION_KEY_ID=k1
SECURITY_CORS_ORIGINS=http://localhost:3000
SECURITY_TRUSTED_PROXY_COUNT=0

# ── AI ───────────────────────────────────────────────────────────────
USE_FAKE_AI=true          # true = no external keys required
AI_PROVIDER=anthropic
AI_ANTHROPIC_API_KEY=
AI_ANTHROPIC_MODEL=
OCR_ENGINE=easyocr
OCR_LANGUAGES=en,ur
FACE_MATCH_THRESHOLD=0.70
FACE_MATCH_REVIEW_LOWER=0.55
CLASSIFIER_MODEL_VERSION=scamclf-v1

# ── Storage ──────────────────────────────────────────────────────────
STORAGE_PROVIDER=s3
STORAGE_ENDPOINT_URL=http://localhost:9002
STORAGE_ACCESS_KEY_ID=minioadmin
STORAGE_SECRET_ACCESS_KEY=minioadmin
STORAGE_BUCKET_DOCUMENTS=trustlens-documents
STORAGE_BUCKET_LISTINGS=trustlens-listings
STORAGE_MAX_UPLOAD_BYTES=10485760
MEDIA_RETENTION_DAYS_IDENTITY=90

# ── Communications ───────────────────────────────────────────────────
EMAIL_PROVIDER=smtp
EMAIL_FROM=no-reply@trustlens.dev
SMTP_HOST=localhost
SMTP_PORT=1025
SMS_PROVIDER=console
OTP_TTL_SECONDS=300

# ── Scoring ──────────────────────────────────────────────────────────
SCORE_VALIDITY_DAYS=30
SCORE_MIN_EVIDENCE_WEIGHT=40
SCORE_RECOMPUTE_DEBOUNCE_SECONDS=10

# ── Frontend ─────────────────────────────────────────────────────────
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_ENV=development
```

`scripts/check-env.py` diffs `.env` against `.env.example` and fails on any key present in the example but
missing locally — so adding a variable in a PR cannot silently break a teammate's machine.
