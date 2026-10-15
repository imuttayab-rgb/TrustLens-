# Security repair and local release report

Prepared 14 October 2026. **The 11 findings from the preceding pre-deployment audit have code fixes and passing targeted checks.** This is a complete source release, including the organized architecture, chat/voice/calls and laptop launchers. It is not a public deployment or a certification of the user's physical laptop.

## Findings and repairs

| Finding | Repair and verified behavior |
| --- | --- |
| F01 — job ownership / raw error disclosure | Database and ARQ metadata paths authorize the job's seller/listing owner. Staff require a staff role plus `job:read`; possession of a job ID grants no access. Results are projected to bounded public fields; failures return a generic message. Owner/outsider and queued/failed cases pass. |
| F02 — access tokens survive logout/reset | Every bearer request checks its active refresh-token family in the database. Rotation retains the family; logout, logout-all, reset/change-password and session revocation invalidate the next request. User-row locking serializes refresh rotation against revocation. Separate legitimate device families remain usable. |
| F03 — OTP/reset secrets in notification logs | Remove obsolete console sender implementations. Local email and SMS previews use loopback Mailpit. Legacy local `console` settings map to the inbox; production rejects local transports, missing credentials and insecure SMTP. Real SMS is explicitly disabled or configured with Twilio. No silent console fallback; API responses never echo OTP codes and disabled SMS is rejected before queueing. |
| F04 — logging/Sentry leaks | Remove raw query values, generate request IDs server-side, redact deep/nested data, unknown objects and formatted exceptions, suppress free-form third-party messages in deployed logs. Sentry exports bounded error types/source basenames only; request tracing is disabled. Configuration errors hide input values. |
| F05 — reset lifetime / single-use races | Reset links expire after 15 minutes. Reset/email/MFA challenge reads lock the token; conditional consume updates reject used/expired tokens. Recovery codes and phone OTPs use conditional one-time consumption. Changes remain inside the unit of work. SQL replay/expiry checks pass. |
| F06 — missing abuse controls / fail-open behavior | Login: 5/minute/IP plus existing 30/15-minute cap; email reset/resend: 3/hour/IP and address; signup: 10/hour/IP and 3/hour/address. Global anonymous/IP and authenticated-user budgets apply. Upload intents: 20/minute/user, 1 GiB reserved bytes and 1,000 files/user by default. Pending intents count; reservations serialize on the user row and signed uploads cannot exceed reserved size. Sensitive limiter outages return retryable 503. Existing chat/voice send limits remain. |
| F07 — chunked body-size bypass | Bound actual received bytes before routing, regardless of Content-Length; streamed oversized bodies return 413. The default API body budget remains the configured image-upload limit plus multipart overhead. Large listing videos use direct, bounded object-storage uploads. |
| F08 — missing browser/error headers | Both Next apps generate fresh CSP nonces and render documents dynamically. Injected unapproved inline scripts are blocked; framework scripts receive a nonce. Explicit runtime API/storage/media origins support hosted configurations. HTTPS configurations emit HSTS; localhost HTTP deliberately does not. API unexpected errors keep security/request-ID headers. |
| F09 — migration TLS downgrade | `DB_SSL_REQUIRE=true` accepts exactly one explicit secure migration `sslmode` (`require`, `verify-ca`, `verify-full`); disable/prefer/allow/duplicate modes are rejected. |
| F10 — personal details in recent history | Browser storage contains only validated listing IDs and timestamps, bounded to 12 items / 30 days. Old full objects are reduced on read. Display details are fetched into memory; Clear history removes the trail. No bearer tokens are persisted. |
| F11 — public operational details | Health endpoints return coarse status only, with readiness failure codes; no versions, environment details or worker job information. |

Additional repairs: API startup now refuses an unavailable job queue instead of returning fictional successful jobs. Backup scripts use materialized files and authenticated encryption verification, avoiding the Windows Docker stdout pipeline failure. Shared source-update helpers verify release checksums, preserve private configuration and restore managed source after a failed build. Removed unused console sender/queue fallback code and an unused import.

## Results

| Check | Result and boundary |
| --- | --- |
| Python unit/API/worker/local launcher suite | **709 passed, 35 skipped**; optional OpenCV-dependent `test_hold_card.py` excluded because OpenCV is unavailable in this execution environment |
| New security regression subset | **38 passed**, included in the 709 above |
| Focused API/crypto/authorization probes | **35 passed**; inventories **187 operations**, probes anonymous/malformed tokens on **157 protected operations** and ordinary users on **38 staff operations** |
| Fresh migration chain + database regressions | **32 passed** on isolated PGlite PostgreSQL WASM: 26 chat/voice/call cases + 6 session/token/quota cases |
| Frontend unit/component tests | **137 passed** in 17 files |
| Web + admin production builds | **Passed** compilation, lint and TypeScript checks; normal Next/ESLint informational warnings remain |
| Browser security checks | **12 passed** in Chromium against the production web build, using synthetic HTTP data |
| Hosted CSP/HSTS configuration, tested locally | **8 passed**, web and admin; per-request nonces and explicit origins verified without deploying |
| Chat/voice UI | **Passed** edit, clear/undo, record/pause/resume/preview, upload retry, playback speed/sequencing/navigation, read-only/support/mobile; fake microphone and synthetic API responses |
| Call controls UI | **Passed** microphone/speaker selection, denied/unavailable device handling, mute persistence, received sound, minimize/end/cleanup and unsupported-browser guidance; synthetic LiveKit adapter |
| Local start/update helper contracts | **13 passed**, included in Python suite: fresh setup and source integrity/rollback, including failed build before stopping services; fake Docker CLI |
| Encrypted backup helper | **Passed** a synthetic multi-chunk 2 MiB round trip, authenticated decryption and plaintext cleanup; not a real volume restore |
| Python undefined/unused-name scan | **Passed** on changed API/shared/database code |

These figures are separate suites with some overlapping coverage; do not add them together as unique scenarios. The 35 skips include database-dependent cases that are covered by the separate database run, plus other unavailable integration fixtures. Check `docs/verification/` for captured evidence. Tests use synthetic accounts/data; they do not alter the user's Windows database.

## Verification limits

### Local updater compatibility repair (14 October 2026)

The first physical-laptop run exposed legacy `IP:port` environment settings being
prefixed with a second loopback IP by the new Compose file. The updater now
normalizes the six public port values, preserves explicit interfaces/custom ports,
and fails before mutation for conflicting interfaces. It saves the original
private config before conversion and restores it on rollback. Credentials and
unrelated config bytes are unchanged. Source verification/backup/copy now flush
file counters so Windows users can observe progress.

The additional regression suite covers legacy/new/quoted/CRLF settings,
invalid/conflicting values, source-and-env rollback, interrupted copying and
secret-free progress output. This is an updater-only repair: the earlier
application test results above were not rerun as a full suite. Actual Docker
Desktop execution still needs the laptop retry.

Targeted validation: **36 passed** (23 compatibility regressions plus the 13
existing launcher/update checks). Captured output: `docs/verification/port-compatibility-tests.txt`.

No Docker CLI/daemon, Windows desktop, live microphones, real LiveKit SFU, external SMS/email providers or native multi-connection PostgreSQL server were available here. Actual Docker image builds, WSL bind mounts, complete volume restore, hardware audio and native database race/load tests are **not marked passed**. PGlite verifies SQL and state transitions; it does not certify native concurrent locking performance. Next builds used a cached Inter font response; normal first-time laptop builds need internet. `scripts/security-check.sh` against a complete running Docker stack was not run here; its authentication/header/error cases are covered by the isolated probes, while a seeded public-score payload and full-stack brute-force check remain laptop checks. No new dependency vulnerability advisory scan or public deployment/post-deployment test was performed.

## Preserved product behavior

Chat originals, voice originals, revisions and audit records remain server-side. A user's clear action only hides that user's view. Edit/delete-for-everyone is limited to 60 seconds; sold/inactive listings retain 72 hours of messaging grace and then become read-only. Calling eligibility and the existing device policy remain in force. This release does not introduce a single-device-account restriction. Identity-document retention is a separate existing 90-day workflow; this report does not claim that every kind of media has indefinite retention.

The updater preserves the existing environment, encryption keys, database and object-store volumes. Source backups and an encrypted database snapshot are created before migration. A source ZIP does not contain the user's records; transfer of an existing installation requires its database, objects and original keys as described in `docs/operations/TRANSFER.md`.

## Reproduction

Install development dependencies from the existing locks, then run from the project root:

```bash
uv run python testing/python/run_unit_tests.py packages/py apps/api/tests apps/worker/tests testing/python -m 'not integration'
uv run python testing/security/run_checks.py --root . --out security-evidence
pnpm --filter @trustlens/web test
pnpm --filter @trustlens/web build
pnpm --filter @trustlens/admin build
TRUSTLENS_ROOT="$PWD" AUDIT_OUT="$PWD/security-evidence" node testing/security/document-headers.mjs
TRUSTLENS_ROOT="$PWD" AUDIT_OUT="$PWD/security-evidence" node testing/security/browser-checks.mjs
TRUSTLENS_ROOT="$PWD" AUDIT_OUT="$PWD/security-evidence" node testing/security/chat-voice-ui.mjs
TRUSTLENS_ROOT="$PWD" AUDIT_OUT="$PWD/security-evidence" node testing/security/call-controls.mjs
```

Database tests require a disposable migrated `CHAT_TEST_DATABASE_URL`; never point tests at the working installation. Chromium security probes require Playwright's browser installation and run with `TRUSTLENS_ROOT` / `AUDIT_OUT` set. On the laptop run the launcher/doctor, then `testing/manual/CHAT_CALL_SMOKE.md` for real audio acceptance. None of these commands deploys the platform.

CSP implementation reference: [official Next.js CSP guide](https://nextjs.org/docs/app/guides/content-security-policy). Nonce-based documents are dynamic and cannot use the former static/ISR HTML caching; this is a deliberate security/performance tradeoff. Rates and quotas are configurable; existing retained files are never deleted to free quota.
