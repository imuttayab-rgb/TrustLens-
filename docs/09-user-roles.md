# 09 — User Roles

## 1. Roles

| Role           | Who                                       | Gets it by                                                        |
| -------------- | ----------------------------------------- | ----------------------------------------------------------------- |
| `BUYER`        | Anyone checking a seller before paying    | Default on registration                                           |
| `SELLER`       | A marketplace seller seeking verification | Self-upgrade (`POST /me/become-seller`) or partner-initiated (A3) |
| `REVIEWER`     | Staff who work the identity/fraud queue   | Granted by an admin                                               |
| `ADMIN`        | System owner                              | Seeded; granted by another admin                                  |
| _(API client)_ | Partner marketplace backend               | Not a user — an `api_clients` row with scoped keys                |

Roles are additive: one person may hold `BUYER` + `SELLER`. `REVIEWER` and `ADMIN` require MFA
([07 §10](07-authentication-authorization.md)).

Anonymous visitors are a real principal too: the public seller page is readable without an account, since
a buyer about to be scammed should not have to register first. Anonymous access is rate-limited by IP and
sees only the public projection of the score.

## 2. Permission matrix

`✔` allowed · `S` own records only · `—` denied

| Permission                                                | Anon | BUYER | SELLER |    REVIEWER     | ADMIN |
| --------------------------------------------------------- | :--: | :---: | :----: | :-------------: | :---: |
| `seller:read:public` — public score page                  |  ✔   |   ✔   |   ✔    |        ✔        |   ✔   |
| `seller:read:self`                                        |  —   |   —   |   S    |        —        |   ✔   |
| `seller:read:any` — full profile incl. verification state |  —   |   —   |   —    |        ✔        |   ✔   |
| `seller:write:self`                                       |  —   |   —   |   S    |        —        |   ✔   |
| `seller:flag` / `seller:suspend`                          |  —   |   —   |   —    |      ✔ / —      |   ✔   |
| `identity:submit`                                         |  —   |   —   |   S    |        —        |   —   |
| `identity:read:self`                                      |  —   |   —   |   S    |        —        |   ✔   |
| `identity:read:any` — view CNIC/selfie images             |  —   |   —   |   —    |        ✔        |   ✔   |
| `identity:approve` / `identity:reject`                    |  —   |   —   |   —    |        ✔        |   ✔   |
| `contact:verify:self` — phone OTP, email                  |  —   |   ✔   |   S    |        —        |   —   |
| `listing:read:self`                                       |  —   |   —   |   S    |        —        |   ✔   |
| `listing:read:any`                                        |  —   |   —   |   —    |        ✔        |   ✔   |
| `listing:write:self`                                      |  —   |   —   |   S    |        —        |   —   |
| `listing:analyse`                                         |  —   |   —   |   S    |        ✔        |   ✔   |
| `trust_score:read:public`                                 |  ✔   |   ✔   |   ✔    |        ✔        |   ✔   |
| `trust_score:read:full` — breakdown + evidence pointers   |  —   |   —   |   S    |        ✔        |   ✔   |
| `trust_score:recompute`                                   |  —   |   —   |   S    |        ✔        |   ✔   |
| `trust_score:override`                                    |  —   |   —   |   —    |        —        |   ✔   |
| `appeal:create`                                           |  —   |   —   |   S    |        —        |   —   |
| `appeal:read:self`                                        |  —   |   —   |   S    |        —        |   ✔   |
| `appeal:read:any`                                         |  —   |   —   |   —    |        ✔        |   ✔   |
| `appeal:assign`                                           |  —   |   —   |   —    |        ✔        |   ✔   |
| `appeal:resolve`                                          |  —   |   —   |   —    |        ✔        |   ✔   |
| `review_case:read` / `review_case:decide`                 |  —   |   —   |   —    |        ✔        |   ✔   |
| `scoring_model:read`                                      |  —   |   —   |   —    |        ✔        |   ✔   |
| `scoring_model:write` / `:simulate` / `:activate`         |  —   |   —   |   —    |        —        |   ✔   |
| `api_client:read`                                         |  —   |   —   |   —    |        —        |   ✔   |
| `api_client:create` / `:update` / `:revoke`               |  —   |   —   |   —    |        —        |   ✔   |
| `audit_log:read`                                          |  —   |   —   |   —    | S (own actions) |   ✔   |
| `user:read:any` / `user:manage_roles`                     |  —   |   —   |   —    |      ✔ / —      |   ✔   |
| `job:read` / `job:retry`                                  |  —   |   —   |   S    |        ✔        |   ✔   |
| `metrics:read`                                            |  —   |   —   |   —    |        ✔        |   ✔   |

Two deliberate restrictions:

- **A reviewer cannot override a trust score.** They can approve/reject evidence, which causes a
  _recomputation_. Only an admin can bypass the engine. This keeps the queue worker's power proportional
  to their job and keeps the audit story clean.
- **A reviewer cannot manage roles.** Otherwise the queue role becomes a privilege-escalation path.

## 3. Journeys

### Buyer

1. Receives a seller link, or searches on `/check`.
2. Opens `/seller/{handle}` — server-rendered, no account needed.
3. Sees the score gauge, risk badge, and the reason list — _why_, not just a number.
4. May register to save checks and report a seller.

### Seller

1. Registers → verifies email → `POST /me/become-seller`.
2. Verification checklist shows four checks with the points each is worth.
3. **Identity:** consents to biometric processing → uploads CNIC front/back + selfie → 202 + job →
   progress UI (_reading CNIC → matching face_) → confirms/corrects the OCR-extracted fields.
4. **Phone:** enters number → OTP → verified.
5. **Email:** already verified at registration; may add a business email.
6. **Device/network:** captured passively, visible under Settings → Devices.
7. Adds listings → each is analysed by the LLM + classifier.
8. Dashboard shows the score, the breakdown, and the ranked improvement list.
9. Disagrees → files an appeal against that specific score → messages the reviewer → notified of the outcome.

### Reviewer

1. Logs in with MFA → `/admin/reviews`, a queue ordered by priority then age.
2. Opens a case: side-by-side CNIC image and selfie, OCR fields, similarity score **and the threshold in
   force**, device cluster, IP reputation, listing findings.
3. Approves or rejects with a reason → recomputation is enqueued → audit-logged.
4. Handles appeals: reads the frozen breakdown, requests more info, or resolves.

### Admin

Everything a reviewer can do, plus: tune `scoring_weights` → simulate → activate a model version;
override a score (reason mandatory); manage API clients and keys; view usage and quotas; read the full
audit log; manage users and roles; retry dead-lettered jobs.

### API client (machine)

1. Admin creates the client and issues a key (shown once).
2. Partner calls `GET /public/v1/sellers/{ref}/trust-score` server-side.
3. Optionally registers a webhook for `SCORE_UPDATED` instead of polling.
4. Monitors usage at `GET /public/v1/usage`; sees `X-RateLimit-*` on every response.

## 4. Role transitions

| From   | To                 | Trigger          | Side effects                                                                               |
| ------ | ------------------ | ---------------- | ------------------------------------------------------------------------------------------ |
| BUYER  | BUYER + SELLER     | Self-service     | Creates `seller_profiles`, opens the verification checklist                                |
| any    | +REVIEWER / +ADMIN | Admin grant      | MFA enrolment required before first privileged action; `perm_version` bumped; audit-logged |
| any    | −role              | Admin revoke     | `perm_version` bumped → existing access tokens rejected within seconds                     |
| ACTIVE | SUSPENDED          | Admin/fraud rule | All sessions revoked; score capped; public page shows "under review"                       |
| ACTIVE | DELETED            | User request     | Soft delete; PII purge job; score history retained anonymised for fraud-pattern integrity  |
