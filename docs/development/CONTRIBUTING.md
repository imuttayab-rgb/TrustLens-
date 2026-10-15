# Developer guide

## Prerequisites and workflows

For normal laptop use choose `START_HERE.md`; Docker supplies all runtimes. For host-based editing use Node 24, pinned pnpm 9.12.3, Python 3.12+, uv, FFmpeg for voice validation, and the local backing services. Use `.env.example` for host development, `.env.production.example` for container mode. Host processes reach `localhost`; containers reach Compose service names. Do not mix the two connection files.

```bash
corepack enable
pnpm install --frozen-lockfile
uv sync --all-packages --dev
# Optional real local vision tests require worker extras:
uv sync --all-packages --dev --extra onnx
```

Run `pnpm --filter @trustlens/web dev` and the matching API/worker commands from the existing Makefile after configuring backing services. Prefer the container launcher for a portable complete demo. Developer installs require internet the first time.

## Naming and boundaries

Python modules/functions/variables use `snake_case`; classes use `PascalCase`; constants use `UPPER_SNAKE_CASE`. React components use `PascalCase.tsx`; hooks use `use-feature.ts` with exported `useFeature`. Plain TS functions/variables use `camelCase`. Public HTTP aliases, database identifiers, migration revisions and generated client names are compatibility contracts: do not rename them as a style exercise.

Keep one ownership boundary per file. UI views accept state/commands and render them. Hooks/services own feature workflows and side effects. Put domain-neutral UI into `packages/ui`, never feature-specific authorization. Access shared exports through feature/package entrypoints. Compatibility barrels and CLI forwarding modules are intentionally small.

## State and errors

Use React Query for API-backed data, local state for drafts/forms, context for app-lifetime media commands, refs for external media handles and cancellation generations. Never persist auth tokens or private chat data to browser storage. The API repeats all critical guards; hiding a button does not authorize an action.

Web/admin profile requests use `createJsonRequester`: bounded requests, one session refresh, JSON-envelope validation, sanitized server failures, caller cancellation, request IDs and typed field errors. Binary audio needs separate transfer handling; voice download/upload are bounded and recording retries retain the same idempotency key. UI boundaries offer recovery for unexpected render failures. Backend exception handlers map domain failures without raw tracebacks; workers retain their existing retry/dead-letter/supervisor behavior. Best-effort cleanup/telemetry failures may be intentionally ignored with an explanation; never blanket-catch a failed business mutation and report success.

## Comments

Module headers explain ownership and purpose. Public services explain access/deadline/transaction rules; comments near side effects explain cancellation, locking, cleanup and compatibility. Do not narrate obvious assignments. Maintain the comment when changing the invariant. Generated schema files carry generator comments and are regenerated, not edited by hand. JSON cannot contain comments; configuration responsibility is documented in `ENVIRONMENT.md` and the file index.

## Verification

```bash
pnpm --filter @trustlens/web typecheck
pnpm --filter @trustlens/admin typecheck
pnpm --filter @trustlens/web test
pnpm --filter @trustlens/web build
pnpm --filter @trustlens/admin build
uv run python testing/python/run_unit_tests.py
uv run pytest testing/python/test_local_setup.py
uv run lint-imports --config .importlinter
```

The unit-test launcher creates ephemeral configuration and dummy endpoints; database tests skip unless separately opted in. `test_hold_card.py` requires the optional OpenCV/NumPy vision dependencies. For integration tests provide `CHAT_TEST_DATABASE_URL` pointing at an isolated, migrated PostgreSQL test database, then run `apps/api/tests/test_chat_retention_voice.py` and `test_voice_calls.py`. Never point tests at a user database.

Use `make codegen` after API contract changes. Review generated diffs. Retention migrations deliberately refuse downgrade; CI applies `upgrade head` twice to check restart safety. Keep dependency lockfiles; do not remove them to fix a build. Run full Docker/image checks on a Docker-capable machine before deploying. Local automated UI tests with fake media do not certify real device routing or TURN.
