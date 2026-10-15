# Organized source release — verification report

Historical architecture baseline. The later security release is documented in [SECURITY_FIX_REPORT.md](SECURITY_FIX_REPORT.md).

Prepared 14 October 2026. This is a complete source distribution with a fresh-machine launcher. It is not a verified image of the user's physical Windows Docker installation and contains no copied user database or live credentials.

## Changes

- Split calling, messaging, profiles, photo protection and authentication application workflows into feature modules. Preserve operator CLI compatibility through small forwarding modules.
- Split the large database model/repository files into domain modules with stable public exports. ORM schema and public table names remain unchanged.
- Separate chat, recording, playback and calling controllers from views. Keep call/player providers above route changes. React Query owns remote records; scoped state/refs own drafts and media lifecycle.
- Consolidate duplicated web/admin JSON request code into the shared API client, with bounded requests, session refresh, malformed-response handling, cancellation, safe errors and field/request context.
- Add bounded binary voice downloads, safe upload retry errors, an admin recovery boundary and generic public HTTP 5xx responses. Keep domain/worker error policies in their existing central layers.
- Centralize public API origins and load backend settings from private environment configuration. Support blank optional classifier thresholds as documented by the template.
- Remove the unused message-response helper, the redundant messages-route forwarding component, and 445 unused imports from the extracted persistence modules. Compatibility barrels are intentional and retained.
- Add 279 missing module-purpose headers and 35 business-invariant method docstrings, plus the comprehensive file responsibility index. Preserve existing meaningful comments and generated-file ownership.
- Update Node runtime guidance/Docker/CI to Node 24; keep the existing pnpm/uv dependency locks. Refresh OpenAPI documentation and generated TS contracts to the current 161 paths.
- Add one-command local start/stop/doctor/log/demo scripts. Generate fresh secrets once, preserve keys on rerun, isolate the new Compose project/images, check errors and readiness, use loopback bindings and support Windows paths with spaces.
- Fix full encrypted backup verification so an early-closing `pg_restore --list` pipe cannot hide incomplete authentication or trigger the previously observed broken-pipe failure.
- Update CI to apply retained-data migrations without destructive downgrades. Add developer, architecture, API, environment, transfer and laptop troubleshooting documentation.

## Checks performed

| Check | Result / scope |
| --- | --- |
| Web production build | Passed; compiled, ESLint/type checks, prerender and route output |
| Admin production build | Passed; compiled, ESLint/type checks and route output |
| Web + admin TypeScript after API regeneration | Passed |
| Web automated tests | 134 passed, including 7 shared transport failure/cancellation contracts |
| Python unit/API-contract/worker + launcher tests | 662 passed, 29 skipped; one optional OpenCV-dependent test file excluded |
| Fresh Alembic migration chain | Passed from empty database through `202610140100` using PGlite PostgreSQL WASM and real migrations |
| Chat/voice/call database regressions | 26 passed against that migrated database, including retained originals, permission denials, 60-second/72-hour limits, idempotency, encryption and call ownership/expiry |
| Schema equivalence | All 77 ORM tables, columns, constraints and indexes compile identically to the original source; all mappers configure |
| Calling UI regression | Passed using actual React controls with synthetic API/LiveKit adapters: routing, denied devices, mute, sound, minimize, late switch completion, cleanup and unsupported-browser guidance |
| Chat/recording/playback UI regression | Passed in Chromium against the actual production Next app with synthetic HTTP responses and fake microphone: edit/clear/undo, capture/pause/resume/preview, retry, sequential playback/speed, navigation, read-only/support/mobile |
| Portable launcher contracts | 4 passed with a fake Docker CLI: new keys, rerun preservation, isolated project names, build failure, missing engine and lock handling |
| Generated configuration | Full local settings parse succeeds with generated keys and calling enabled |
| Python undefined-name scan | Passed across API, worker and Python packages |
| Configuration/package checks | Compose YAML parsing and backend/frontend secret separation; local shell syntax; ZIP/private-file/path checks recorded during packaging |

Next builds used a local cached Inter font response because external font fetching is restricted in this environment. The shipped app keeps its normal Next font configuration; first build on a laptop needs internet. Database tests used the PostgreSQL WASM engine, not a Dockerized PostgreSQL 16 server. UI media adapters/fake capture do not certify a real SFU audio path or actual hardware routing.

## Verification limits and handoff

Docker CLI/daemon were unavailable here, so real container image builds, Docker Desktop/WSL startup, Windows bind mounts and a full volume restore were not executed. Run `START_LOCAL.bat`, `CHECK_LOCAL.bat` and `testing/manual/CHAT_CALL_SMOKE.md` on the target laptop. Real microphones, phone speaker routing, TURN/firewalls and public deployment still require real-device/network checks. The optional vision test file requires OpenCV/NumPy; some other tests intentionally skip without external/integration fixtures. The complete CI matrix and load/security audits are not claimed as passed.

This release improves the identified architecture and failure boundaries; it does not claim that every historic endpoint was rewritten, every latent bug removed, or the system load-tested for an unspecified production scale. Some established routers still compose query projections and some UI forms own local form state. The existing verified-device policy has not been expanded into a new single-device login restriction.

The complete source can be moved to another laptop. Existing data requires a coordinated database/object/key/queue transfer described in `docs/operations/TRANSFER.md`; a source ZIP alone cannot move Docker volume contents.
