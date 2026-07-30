# ADR-0006: JWT access tokens + rotating refresh cookies with reuse detection

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Haseeb Ur Rehman, Muhammad Muttayab

## Context

The proposal does not specify an authentication mechanism (assumption A5). The system holds CNIC images,
selfies, and face embeddings, and admin accounts can override trust scores — so session compromise is a
high-impact event, not a nuisance.

## Decision

- **Access token:** JWT, EdDSA (Ed25519), 15-minute lifetime, held **in browser memory only**.
- **Refresh token:** opaque 256-bit random value, hashed in the database, delivered in an
  `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth` cookie, 30-day absolute / 7-day idle lifetime.
- **Rotation on every use**, within a `family_id`. Presenting an already-rotated token is treated as
  theft: the entire family is revoked, `perm_version` is bumped, a CRITICAL event is logged, and the user
  is notified.
- **`perm_version` claim** compared against a Redis counter on each request, so a role change or
  suspension takes effect in seconds rather than waiting out the token lifetime.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **Server-side sessions in Redis** | Simple and revocable, but makes every request a Redis round-trip and couples the API to session storage. The `perm_version` counter gives most of the revocability at a fraction of the cost |
| **Long-lived JWT, no refresh** | A stolen token is valid until expiry with no revocation path. Unacceptable given the data at stake |
| **Both tokens in `localStorage`** | Readable by any XSS payload. In an application holding biometric data, this is not an acceptable residual risk |
| **Non-rotating refresh token** | A stolen refresh token becomes a 30-day skeleton key with no detection mechanism |
| **Third-party auth provider (Auth0/Clerk/Supabase Auth)** | Faster to build, but adds a vendor dependency and an external cost, and the FYP is partly assessed on demonstrating the auth design — outsourcing it removes something the project should show |
| **HS256 symmetric JWT** | Acceptable for a single service, but forecloses letting a future extracted service verify tokens without holding the signing key |

## Consequences

**Positive**
- XSS cannot read the refresh token (httpOnly) and the access token dies with the tab.
- A stolen refresh token is **self-limiting**: whichever party uses the older copy triggers revocation of
  both sessions.
- Stateless verification on the hot path; one cheap Redis GET for revocation checking.
- Asymmetric signing keeps the service-extraction option open.

**Negative / accepted costs**
- More moving parts than a session cookie: rotation, families, reuse detection, and `perm_version` all
  need tests.
- The refresh cookie makes `/auth/refresh` a CSRF target, requiring `SameSite`, a scoped `Path`, a
  double-submit token, and an Origin check ([07 §8](../07-authentication-authorization.md)).
- Access-token claims can be up to 15 minutes stale for anything not covered by `perm_version`.

**Revisit if:** the system needs SSO or social login, at which point an OIDC provider becomes worth the
dependency — the token handling above would remain, with the provider replacing only the credential step.
