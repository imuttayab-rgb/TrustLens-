# 06 — API Design

## 1. Two APIs, one codebase

| | Internal API | Public (partner) API |
|---|---|---|
| Base path | `/api/v1` | `/public/v1` |
| Consumers | `apps/web` (browser) | Marketplace backends (server-to-server) |
| Auth | JWT bearer / httpOnly cookie | `Authorization: Bearer tl_live_…` API key |
| Contains PII | Yes (own data only) | **No** |
| Rate limit | Per user | Per API key + per client quota |
| Breaking-change policy | Frontend ships in the same commit | Versioned and deprecation-noticed |
| Docs | `/docs` (Swagger, non-prod only) | Public reference + Postman collection |

> **WHY split them rather than one API with two auth methods:** the public surface must be able to evolve
> slowly and never leak a field that was added for the seller dashboard. A separate router tree with its
> own response schemas makes "no PII in the public API" a structural property (the schema simply has no
> such field) rather than a review checklist item.

## 2. Versioning

- URL-path versioning (`/api/v1`, `/public/v1`) — trivially visible in logs, curl, and Postman.
- **Additive changes** (new optional field, new endpoint) ship inside `v1`.
- **Breaking changes** (removing/renaming a field, changing a type, tightening validation) require `v2`.
- Public API deprecation: `Deprecation` and `Sunset` headers plus a `warnings[]` entry in `meta`,
  minimum 90 days' notice, and a changelog in the docs.
- `X-TrustLens-Version` response header carries the build SHA for support triage.

## 3. Response format

### Success

```jsonc
{
  "data": { "id": "018f…", "score": 82, "riskLevel": "LOW" },
  "meta": { "requestId": "req_01HX…", "timestamp": "2026-07-30T12:00:00Z" }
}
```

Collections add pagination to `meta`:

```jsonc
{
  "data": [ /* … */ ],
  "meta": {
    "requestId": "req_01HX…",
    "timestamp": "2026-07-30T12:00:00Z",
    "pagination": { "page": 2, "perPage": 20, "total": 137, "totalPages": 7,
                    "hasNext": true, "hasPrev": true }
  }
}
```

Cursor collections use `{"cursor": {"next": "eyJ…", "prev": null, "hasNext": true}}` instead.

JSON is **camelCase** on the wire, `snake_case` in Python. Pydantic's `alias_generator=to_camel` with
`populate_by_name=True` does the translation once, at the schema layer — neither codebase compromises its
own idiom.

### Errors — RFC 9457 `application/problem+json`

```jsonc
{
  "type": "https://api.trustlens.app/errors/validation-failed",
  "title": "Validation failed",
  "status": 422,
  "detail": "One or more fields are invalid.",
  "instance": "/api/v1/verification/phone/request-otp",
  "code": "VALIDATION_FAILED",
  "requestId": "req_01HX…",
  "timestamp": "2026-07-30T12:00:00Z",
  "errors": [
    { "field": "phoneNumber", "code": "INVALID_FORMAT",
      "message": "Phone number must be in E.164 format, e.g. +923001234567" }
  ]
}
```

Rules:
- `code` is a **stable machine string**; the frontend switches on `code`, never on `title` or `detail`.
- `errors[].field` uses dotted paths (`address.city`, `images.0.file`) so React Hook Form can map them
  straight onto inputs.
- 5xx `detail` is always the generic string; the real cause is logged against `requestId`.
- Chosen over a bespoke `{success:false,…}` envelope because problem+json is an IETF standard with
  existing client support, and because a proper HTTP status plus a typed body is what partner
  integrators expect.

### Status codes

`200` OK · `201` Created (+ `Location`) · `202` Accepted (async job started) · `204` No Content ·
`400` malformed · `401` unauthenticated · `403` unauthorised · `404` not found · `409` conflict/version
mismatch · `410` gone (revoked key) · `413` payload too large · `422` validation/invalid state ·
`429` rate limited (+ `Retry-After`, `X-RateLimit-*`) · `500` · `502` upstream AI failure ·
`503` degraded/maintenance.

## 4. Internal API endpoints (`/api/v1`)

### Auth
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | Creates user, sends verification email, 201 |
| POST | `/auth/login` | Returns access token; sets refresh cookie |
| POST | `/auth/refresh` | Rotates refresh token, reuse detection |
| POST | `/auth/logout` | Revokes the current refresh token |
| POST | `/auth/logout-all` | Revokes every family for the user |
| POST | `/auth/verify-email` | Consumes the emailed token |
| POST | `/auth/resend-verification` | Throttled |
| POST | `/auth/forgot-password` | Always 202 — never reveals whether the email exists |
| POST | `/auth/reset-password` | Token + new password; revokes all sessions |
| POST | `/auth/change-password` | Authenticated; requires the current password |
| GET | `/auth/sessions` | Active devices/sessions |
| DELETE | `/auth/sessions/{id}` | Sign out one device |

### Me & seller profile
`GET/PATCH /me` · `GET /me/permissions` · `POST /me/become-seller` ·
`GET/PATCH /sellers/me` · `GET /sellers/{id}` · `GET /sellers` (admin, filterable)

### Verification
| Method | Path | Notes |
|---|---|---|
| POST | `/files/upload-intent` | → presigned PUT URL + `fileId` |
| POST | `/verification/identity` | Body: `{cnicFrontFileId, cnicBackFileId, selfieFileId, consentId}` → **202** + `jobId` |
| GET | `/verification/identity` | Current status + OCR fields the seller may correct |
| POST | `/verification/identity/{id}/confirm` | Seller confirms/corrects OCR-extracted fields |
| POST | `/verification/phone/request-otp` | Throttled: 3/hour, 10/day |
| POST | `/verification/phone/verify-otp` | Max 5 attempts per code |
| DELETE | `/verification/phone/{id}` | |
| POST | `/verification/email/add` | |
| POST | `/verification/email/resend` | |
| GET | `/verification/status` | All four checks in one call (dashboard) |
| POST | `/verification/device` | Submits the client fingerprint payload |
| GET | `/verification/devices` | Devices linked to this account |

### Listings
`GET /listings` · `POST /listings` (202, queues analysis) · `GET /listings/{id}` ·
`PATCH /listings/{id}` · `DELETE /listings/{id}` (soft) ·
`POST /listings/{id}/analyse` (re-run, rate-limited) · `GET /listings/{id}/analysis`

### Trust score
| Method | Path | Notes |
|---|---|---|
| GET | `/sellers/{id}/trust-score` | Current score + full breakdown |
| GET | `/sellers/{id}/trust-score/history` | Paginated history (score-over-time chart) |
| GET | `/sellers/{id}/trust-score/improvements` | Ranked "what to fix" list, derived from unearned points |
| POST | `/sellers/{id}/trust-score/recompute` | Admin/self, rate-limited, idempotent, 202 |

`GET /sellers/{id}/trust-score` response shape:

```jsonc
{
  "data": {
    "sellerId": "018f…",
    "score": 74,
    "riskLevel": "LOW",
    "confidence": 0.91,
    "modelVersion": "v1.0",
    "computedAt": "2026-07-30T11:58:04Z",
    "validUntil": "2026-08-29T11:58:04Z",
    "capApplied": null,
    "categories": [
      { "category": "IDENTITY", "pointsAwarded": 30, "pointsPossible": 30, "status": "PASS" },
      { "category": "PHONE",    "pointsAwarded": 10, "pointsPossible": 15, "status": "PARTIAL" }
    ],
    "signals": [
      { "code": "IDENTITY_FACE_MATCH", "category": "IDENTITY", "status": "PASS",
        "pointsAwarded": 15, "pointsPossible": 15, "confidence": 0.97,
        "reasonCode": "FACE_MATCH_HIGH",
        "reasonText": "Selfie matches the photo on the submitted CNIC." },
      { "code": "PHONE_NOT_DISPOSABLE", "category": "PHONE", "status": "FAIL",
        "pointsAwarded": 0, "pointsPossible": 5, "confidence": 0.88,
        "reasonCode": "PHONE_LINE_TYPE_VOIP",
        "reasonText": "The phone number is an internet (VOIP) number rather than a mobile SIM." }
    ],
    "unavailableSignals": ["LISTING_PRICE_REALISTIC"],
    "summary": "Identity is fully verified. The phone number is an internet number, which is common with throwaway accounts."
  },
  "meta": { "requestId": "req_01HX…", "timestamp": "…" }
}
```

Every number in that payload comes straight from `trust_score_signals` — the API performs no scoring
logic of its own.

### Appeals
`GET /appeals` · `POST /appeals` · `GET /appeals/{id}` · `POST /appeals/{id}/messages` ·
`POST /appeals/{id}/withdraw`

### Jobs & notifications
`GET /jobs/{id}` (`{status, progress, stage, result, error}`) · `GET /jobs/{id}/stream` (SSE, optional) ·
`GET /notifications` · `POST /notifications/{id}/read` · `POST /notifications/read-all`

### Admin (`/api/v1/admin`, permission-gated)
| Area | Endpoints |
|---|---|
| Reviews | `GET /reviews` · `POST /reviews/{id}/assign` · `POST /reviews/{id}/decide` |
| Sellers | `GET /sellers` · `POST /sellers/{id}/flag` · `POST /sellers/{id}/suspend` |
| Identity | `GET /identity-verifications/{id}` · `POST /identity-verifications/{id}/override` |
| Scores | `POST /sellers/{id}/trust-score/override` (reason required) |
| Scoring models | `GET/POST /scoring-models` · `PATCH /scoring-models/{id}` · `POST /{id}/activate` · `POST /{id}/simulate` |
| Appeals | `GET /appeals` · `POST /appeals/{id}/assign` · `POST /appeals/{id}/resolve` |
| API clients | full CRUD · `POST /api-clients/{id}/keys` · `DELETE /api-keys/{id}` · `GET /api-clients/{id}/usage` |
| Audit | `GET /audit-logs` |
| Ops | `GET /metrics/overview` · `GET /jobs/dead-letter` · `POST /jobs/{id}/retry` |

`POST /scoring-models/{id}/simulate` deserves note: it recomputes a sample of sellers against a
**draft** model and returns the score distribution delta. Activating weights blind, across every seller,
is not a decision anyone should make without seeing what it does first.

## 5. Public API endpoints (`/public/v1`)

| Method | Path | Scope | Notes |
|---|---|---|---|
| GET | `/sellers/{sellerRef}/trust-score` | `score:read` | `sellerRef` = TrustLens id, handle, or `{marketplaceSlug}:{externalRef}` |
| POST | `/sellers/lookup` | `score:read` | Batch, max 50 refs, one round trip |
| POST | `/sellers` | `seller:write` | Partner-initiated onboarding (A3); returns an invite link |
| GET | `/sellers/{sellerRef}/status` | `score:read` | Lightweight: verification states only |
| GET | `/webhooks` / POST / DELETE | `webhook:manage` | Manage endpoints |
| GET | `/status` | none | Health + current scoring model version |

Public score payload — the internal shape minus PII, plus a documented cache header:

```jsonc
{
  "data": {
    "sellerRef": "olx:seller-99213",
    "score": 74,
    "riskLevel": "LOW",
    "confidence": 0.91,
    "verifications": { "identity": "VERIFIED", "phone": "VERIFIED",
                       "email": "VERIFIED", "device": "PASS" },
    "reasons": [
      { "code": "IDENTITY_VERIFIED", "impact": "POSITIVE",
        "text": "Government ID verified with a matching selfie." },
      { "code": "PHONE_LINE_TYPE_VOIP", "impact": "NEGATIVE",
        "text": "Phone number is an internet number rather than a mobile SIM." }
    ],
    "modelVersion": "v1.0",
    "computedAt": "2026-07-30T11:58:04Z",
    "expiresAt": "2026-08-29T11:58:04Z"
  },
  "meta": { "requestId": "req_01HX…", "cached": true, "timestamp": "…" }
}
```

`Cache-Control: public, max-age=300` plus `ETag` — a partner polling every request still costs one Redis
read, and a well-behaved client gets a 304.

## 6. Validation strategy

Four layers, each catching what the previous cannot:

| Layer | Enforces | Failure |
|---|---|---|
| Client (Zod) | Format, required, length | Inline field error, no request |
| API schema (Pydantic v2) | Types, ranges, formats, enums, cross-field rules | 422 with `errors[]` |
| Domain (value objects + policies) | Business invariants (valid CNIC checksum, weights sum to 100, one open appeal) | Typed `DomainError` |
| Database | Structural truth (FK, unique, check, not-null) | 409/500 — a bug if reached |

Standing rules: never trust client-supplied `Content-Type` for uploads (sniff magic bytes); never accept
a client-supplied `userId` (always derive the actor from the token); normalise before validating
(trim, lowercase email, E.164 phone) so equivalent inputs cannot create duplicates; cap every string and
array (`title ≤ 250`, batch lookup ≤ 50, page size ≤ 100).

## 7. Pagination, filtering, sorting, search

**Pagination — two modes, chosen deliberately.**

| Mode | Params | Used for | Why |
|---|---|---|---|
| Offset | `?page=2&perPage=20` | Admin tables | Users need "page 7 of 12" and a total count |
| Cursor | `?cursor=eyJ…&limit=20` | Score history, audit logs, request logs, notifications | Stable under concurrent inserts and O(1) on huge partitioned tables |

Offset pagination on `audit_logs` would drift (new rows shift the window) and get slower with depth;
cursor pagination on an admin table would remove the page numbers reviewers need. Neither is universally
right, so the choice is per-endpoint and documented.

**Filtering** — explicit, typed query params only; no generic query DSL:
`?status=OPEN&riskLevel=HIGH&createdFrom=2026-01-01&createdTo=2026-06-30&marketplaceId=…`.
Repeated params mean OR (`?status=OPEN&status=UNDER_REVIEW`); different params mean AND.
A generic `?filter[field][op]=value` DSL is rejected: it is an injection surface, it cannot be typed in
OpenAPI, and it makes it impossible to guarantee an index exists for every expressible query.

**Sorting** — `?sort=-createdAt,score`; `-` = descending. Each endpoint declares an **allowlist** of
sortable fields (rejected with 422 otherwise) so a sort can never hit an unindexed column.

**Search** — `?q=…`, minimum 2 characters, matched with `pg_trgm` against a fixed per-resource field set
(sellers: `display_name`, `handle`, `email`; listings: `title`). Always paired with pagination.

## 8. Idempotency

Unsafe operations that trigger cost (score recomputation, LLM analysis, SMS, partner seller creation)
accept `Idempotency-Key: <uuid>`. The middleware stores `key → (status, body, request fingerprint)` in
Redis for 24 h. A replay with the same key and same body returns the stored response; the same key with a
**different** body returns 422 `IDEMPOTENCY_KEY_REUSED`. Required on `/public/v1` writes, optional
internally. Without this, a partner's retry-on-timeout doubles our LLM bill and creates duplicate sellers.

## 9. Rate limiting

| Scope | Limit | Key |
|---|---|---|
| Anonymous | 60 req/min | IP |
| Authenticated | 300 req/min | user id |
| Login | 5 per 15 min, then exponential lockout | IP + email |
| OTP send | 3/hour, 10/day | user + phone |
| OTP verify | 5 per code | otp id |
| File upload intent | 20/hour | user |
| Listing analysis | 10/day | seller |
| Score recompute | 5/hour | seller |
| Public API — free tier | 60/min, 10k/month | api key |
| Public API — partner tier | 600/min, 1M/month | api key |

Redis token bucket. Responses carry `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`;
429 carries `Retry-After`. The tiered limits on OTP and analysis are not politeness — they cap the
direct financial cost of abuse (SMS charges and LLM tokens).

## 10. OpenAPI & tooling

- FastAPI generates `/openapi.json`; a CI job exports it to `docs/api/openapi.json` and fails the build if
  it changed without a regenerated TS client.
- Swagger UI at `/docs` and ReDoc at `/redoc` — **disabled in production** for the internal API, public
  for `/public/v1`.
- Every endpoint declares `summary`, `description`, `tags`, `responses` (including error shapes), and at
  least one request/response **example** — examples are what make a Postman collection and a partner
  integration actually work.
- `scripts/export-postman.sh` converts the OpenAPI doc into the Postman collection the proposal lists as a
  project tool; it is committed so the demo never depends on someone's local Postman workspace.
