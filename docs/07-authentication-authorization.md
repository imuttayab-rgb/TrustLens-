# 07 — Authentication & Authorization

> **ASSUMPTION A5:** the proposal does not specify an auth mechanism. This design uses email+password
> with a short-lived JWT access token and a rotating refresh token in an httpOnly cookie, plus RBAC.

## 1. Identity model

| Principal                                    | Credential                     | Carries                             |
| -------------------------------------------- | ------------------------------ | ----------------------------------- |
| **User** (buyer / seller / reviewer / admin) | password (+ optional TOTP MFA) | JWT access token                    |
| **API client** (partner marketplace)         | API key                        | scopes, quota tier                  |
| **System** (worker jobs)                     | none — in-process              | `actor_type = SYSTEM` in audit logs |

Three principal types means authorisation checks must never assume "there is a current user". Every
audit row records `actor_type` explicitly.

## 2. Registration flow

```
POST /api/v1/auth/register  { email, password, fullName, accountType }
   │
   ├─ Validate: email format + normalise; password ≥ 12 chars, checked against a common-password list
   ├─ Reject disposable email domains at registration for SELLER accounts (soft-warn for buyers)
   ├─ Hash password with argon2id (m=64MB, t=3, p=4)
   ├─ INSERT users (status = PENDING) + user_roles (BUYER or SELLER)
   ├─ INSERT consents (TERMS, PRIVACY — version-stamped)
   ├─ INSERT verification_tokens (EMAIL_VERIFICATION, hashed, 24h TTL)
   ├─ Record access_event + device + ip  (device/network signals start at registration)
   └─ Enqueue send_verification_email
   ↓
201 Created  { userId, email, status: "PENDING" }   ← no tokens issued until email is verified
```

Design points:

- **argon2id, not bcrypt.** Memory-hard, GPU-resistant, and the current OWASP recommendation. Parameters
  live in config so they can be raised as hardware improves; the hash string records its own parameters,
  so old hashes stay verifiable and are transparently re-hashed on next successful login.
- **No auto-login before email verification.** Email verification is a scored signal (F3); letting an
  unverified account operate would let a scammer skip it.
- **Registration is enumeration-safe**: a duplicate email returns the same 201-shaped response and sends
  a "someone tried to register with your address" email instead of leaking that the account exists.

## 3. Login flow

```
POST /api/v1/auth/login  { email, password, deviceFingerprint? }
   │
   ├─ Rate limit: 5 attempts / 15 min per (IP + email)
   ├─ Constant-time lookup + verify (a dummy hash is verified when the user is absent,
   │  so response timing does not reveal account existence)
   ├─ Check: status ACTIVE, not locked_until, email_verified_at IS NOT NULL
   ├─ On failure: failed_login_count++, lock after 10 (exponential), audit log, generic 401
   ├─ If mfa_enabled → 200 { mfaRequired: true, mfaToken }  (short-lived, single-purpose)
   ├─ Issue access token (JWT, 15 min, in the response body → stored in memory)
   ├─ Issue refresh token (opaque 256-bit random, 30 days, new family_id)
   │     Set-Cookie: tl_rt=…; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; Max-Age=2592000
   ├─ Upsert device + user_devices; record access_event with ip_address_id
   └─ Reset failed_login_count, set last_login_at
```

> **WHY access token in memory and refresh token in an httpOnly cookie:** a token in `localStorage` is
> readable by any XSS payload — this application holds CNIC images and biometric data, so token theft is
> not an acceptable residual risk. A memory-only access token dies with the tab, and the httpOnly refresh
> cookie is unreachable from JavaScript. `SameSite=Lax` plus `Path=/api/v1/auth` narrows CSRF exposure to
> exactly one endpoint, which is additionally protected by a double-submit token (§8).

## 4. Access token (JWT)

Algorithm **EdDSA (Ed25519)** with asymmetric keys — the API signs, and any future extracted service can
verify without holding the signing key. HS256 is acceptable for a single-service deployment but forecloses
that option.

```jsonc
{
  "iss": "https://api.trustlens.app",
  "aud": "trustlens-web",
  "sub": "018f2c3d-…", // user id
  "jti": "018f2c4a-…", // for targeted revocation
  "iat": 1753876800,
  "exp": 1753877700, // +15 min
  "typ": "access",
  "roles": ["SELLER"],
  "perms": ["seller:read:self", "listing:write:self", "appeal:create"],
  "pv": 7, // permission version — see below
  "sid": "018f2c50-…", // session/refresh-family id
}
```

`pv` (permission version) solves the standard "stateless tokens can't be revoked" problem without making
every request hit the database. A counter in Redis, `perm_version:{user_id}`, is bumped whenever a user's
roles change or they are suspended. The auth dependency compares `pv` against the cached counter — one
Redis GET, ~0.2 ms — and rejects the token if stale, forcing a refresh. A revoked admin therefore loses
access in seconds, not in up to 15 minutes.

Never in a JWT: PII (email, name, phone), CNIC data, anything secret. A JWT is signed, **not encrypted** —
anyone holding it can read the payload.

## 5. Refresh token rotation with reuse detection

```
POST /api/v1/auth/refresh    (cookie only, no body)
   │
   ├─ Hash the presented token → SELECT … FOR UPDATE
   ├─ Not found            → 401
   ├─ Expired              → 401
   ├─ revoked_at IS NOT NULL  ⇒ ★ REUSE DETECTED
   │       ├─ Revoke EVERY token in family_id (reason = REUSE_DETECTED)
   │       ├─ Bump perm_version → all access tokens for the user die immediately
   │       ├─ CRITICAL log + audit row + notify the user by email
   │       └─ 401 TOKEN_REUSE_DETECTED  (user must log in again)
   ├─ Valid → revoke the old token (reason = ROTATED), issue a new one in the SAME family
   │          with parent_id = old.id
   └─ Return a new access token + Set-Cookie with the new refresh token
```

Rotation with family revocation is what makes a stolen refresh token _self-limiting_: whoever uses the
older copy second triggers the alarm and both parties are logged out. Without rotation, a stolen refresh
token is a 30-day skeleton key.

Refresh tokens are also revoked on: logout, logout-all, password change, password reset, role change,
account suspension, and "sign out this device".

## 6. Roles, permissions, RBAC

**RBAC with permissions**, not role-string checks. `if user.role == "ADMIN"` scattered through routers is
how a reviewer accidentally gains the ability to activate scoring models.

Permission key format: `resource:action[:scope]`, e.g. `seller:read:self`, `seller:read:any`,
`identity:approve`, `scoring_model:activate`, `appeal:resolve`, `api_client:create`, `audit_log:read`.

The `:self` / `:any` scope suffix is deliberate: a seller and an admin both "read a seller", but only one
may read someone else's. Encoding scope in the permission keeps the check in one place
(`require_permissions("seller:read:any")` plus an ownership guard) instead of duplicating an
`if resource.owner_id != user.id` branch at every call site.

Full matrix: [09 — User Roles](09-user-roles.md).

### Enforcement in FastAPI

```python
@router.post(
    "/admin/scoring-models/{model_id}/activate",
    dependencies=[Depends(require_permissions("scoring_model:activate"))],
)
async def activate_model(...): ...
```

Three composable dependencies:

- `get_current_user` — decodes the JWT, validates `pv`, loads a cached principal
- `require_roles(*roles)` — coarse gate for whole route groups
- `require_permissions(*perms)` — fine gate on individual actions
- `require_ownership(resource_loader)` — object-level check for `:self` permissions

**Object-level authorisation is mandatory and separate.** Route-level permission answers "may this role do
this kind of thing"; ownership answers "may this user touch _this row_". Skipping the second is IDOR —
`GET /api/v1/listings/{id}` with a permission check alone would let any seller read any other seller's
listing. Every resource-scoped handler resolves the object and asserts ownership (or `:any`) before acting.

## 7. API-key authentication (public API)

```
Key format:   tl_live_<10-hex id>.<43-char secret>             (tl_test_… for sandbox)
              The '.' separator is deliberate: the prefix itself contains
              underscores, so splitting on '_' would be ambiguous.
Stored:       key_prefix (indexed, plaintext) + key_hash (argon2id of the secret)
Shown:        once, at creation. Never retrievable.
```

Verification: parse the prefix → indexed lookup → argon2 verify in constant time → check `status`,
`expires_at`, `allowed_ips`, and scope for the route → touch `last_used_at` asynchronously.

Scopes: `score:read`, `seller:write`, `webhook:manage`, `usage:read`. A key gets the minimum set.

Rotation: a client may hold two active keys so a rotation is zero-downtime (create new → migrate →
revoke old). Revocation is instant (`status = REVOKED`), unlike a JWT.

Webhook authenticity runs the other way: TrustLens signs outbound payloads with
`X-TrustLens-Signature: t=<ts>,v1=<HMAC-SHA256(secret, ts + "." + body)>` and includes a timestamp so
partners can reject replays.

## 8. CSRF

The API is token-based, but the refresh endpoint is cookie-based, which is exactly the case CSRF exploits.
Layered defence:

1. `SameSite=Lax` on the refresh cookie — blocks cross-site POSTs from third-party pages.
2. `Path=/api/v1/auth` — the cookie is not even sent to any other endpoint.
3. **Double-submit token** on `/auth/refresh` and `/auth/logout`: a non-httpOnly `tl_csrf` cookie whose
   value must be echoed in `X-CSRF-Token`. Same-origin policy prevents an attacker's page from reading it.
4. `Origin`/`Referer` allowlist check on all state-changing requests.
5. All other endpoints use `Authorization: Bearer`, which browsers never attach automatically.

## 9. Protected routes on the frontend

Three layers, because each defends a different thing:

| Layer                                                            | Where               | Defends against                                                                    |
| ---------------------------------------------------------------- | ------------------- | ---------------------------------------------------------------------------------- |
| Edge middleware (`middleware.ts`)                                | Before any JS ships | Unauthenticated users seeing a protected shell; wrong-role users reaching `/admin` |
| Server component guard (`requireRole()` in `(admin)/layout.tsx`) | Server render       | A forged/expired cookie that passed the cheap edge check                           |
| API authorisation                                                | Backend             | Everything — this is the **only** layer that is actually security                  |

The first two are UX. Stating that explicitly matters: frontend guards can always be bypassed with curl,
so no endpoint may rely on them.

Unauthenticated access to a protected route redirects to `/login?next=<path>`; wrong-role access returns
403 rather than redirecting to login, because redirecting a logged-in reviewer to a login page is a
confusing dead end.

## 10. MFA (optional, for ADMIN and REVIEWER)

TOTP (RFC 6238), 30-second step, ±1 window tolerance, secret envelope-encrypted at rest, 10 single-use
recovery codes stored hashed. **Required** for any account with `ADMIN` or `REVIEWER` roles, since those
accounts can override trust scores and read identity documents — the highest-value targets in the system.

## 11. Session security summary

| Control                                     | Value                                                                             |
| ------------------------------------------- | --------------------------------------------------------------------------------- |
| Access token lifetime                       | 15 min                                                                            |
| Refresh token lifetime                      | 30 days (absolute), 7 days idle                                                   |
| Refresh rotation                            | Every use, with family reuse detection                                            |
| Max concurrent sessions                     | 5 per user (oldest evicted)                                                       |
| Password                                    | argon2id, ≥12 chars, common-password blocklist, no forced rotation (NIST 800-63B) |
| Login lockout                               | 5/15 min soft, exponential lock after 10                                          |
| MFA                                         | Optional for sellers/buyers, **mandatory** for admin/reviewer                     |
| Password change                             | Revokes all sessions except the current one                                       |
| Email/phone change                          | Requires re-verification and re-scores the affected signal                        |
| Suspicious login (new device + new country) | Email alert + optional step-up challenge                                          |
