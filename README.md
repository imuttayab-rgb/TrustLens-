# TrustLens — complete organized security release

Marketplace, seller verification, administration, retained messaging, voice messages and browser voice calls. This folder is a complete source distribution, not an incremental patch. Start with [START_HERE.md](START_HERE.md).

## Update this laptop

From the newly extracted release folder, with the existing stack running:

```bash
bash scripts/local/update-existing.sh "$HOME/Documents/TrustLens" trustlens
```

Read [existing-install update instructions](docs/operations/UPDATE_EXISTING.md) and the [security repair report](docs/development/SECURITY_FIX_REPORT.md). This preserves the old installation's environment, accounts and volumes; the source ZIP contains no user database.

## Run locally on a fresh laptop

Install Docker Desktop (Linux containers / WSL 2 on Windows) and Git for Windows. Extract this folder outside the old checkout. Start Docker Desktop, then double-click **START_LOCAL.bat**, or run in Git Bash:

```bash
bash scripts/local/start.sh
```

The launcher creates private per-install configuration, builds the API/worker/web/admin, starts PostgreSQL, Redis, MinIO, Mailpit and LiveKit, applies migrations, and checks readiness. It uses the separate Compose project `trustlens-clean`. It does not import your old computer's records.

| Service | Default local URL |
| --- | --- |
| Marketplace | http://localhost:3000 |
| Administration | http://localhost:3001 |
| API | http://localhost:8000 |
| Development email inbox | http://localhost:8025 |

Optional demo accounts: `bash scripts/local/demo.sh`, then see [CREDENTIALS.dev.md](CREDENTIALS.dev.md). Stop with **STOP_LOCAL.bat**; volumes and records are retained. Never use `down -v` on data you need.

## Structure

| Path | Responsibility |
| --- | --- |
| `apps/web/src/app` | Next.js routes and layout composition |
| `apps/web/src/features` | Feature UI, controllers/hooks and API adapters |
| `apps/admin` | Staff review and administration UI |
| `apps/api/src/trustlens_api/api` | Versioned HTTP routes, schemas and authorization dependencies |
| `apps/api/src/trustlens_api/modules` | Calling, messaging, profile, photo and authentication orchestration |
| `apps/worker` | Background jobs and retry/recovery supervision |
| `apps/ml` | Offline training and evaluation; excluded from deployed application imports |
| `packages/py/trustlens-core` | Framework-independent business rules and use cases |
| `packages/py/trustlens-db` | Domain-grouped models, repositories and transaction unit of work |
| `packages/py/trustlens-shared` | Typed configuration, logging, encryption and external adapters |
| `packages/py/trustlens-ai` | AI ports/adapters and deterministic demo engines |
| `packages/api-client` | Generated types, typed errors and shared JSON request transport |
| `packages/ui`, `packages/config-*` | Reusable UI and shared tooling conventions |
| `database/migrations` | Versioned, ordered database changes |
| `docker`, `scripts/local` | Container definitions and portable localhost launchers |
| `testing`, `**/tests`, `**/*.test.*` | Test infrastructure and regression checks |
| `docs` | Architecture, setup, operations, feature rules and file index |

## Read next

- [Architecture](ARCHITECTURE.md)
- [Developer guide: boundaries, state, errors and comments](docs/development/CONTRIBUTING.md)
- [API structure and extension guide](docs/development/API_STRUCTURE.md)
- [Environment variables](docs/development/ENVIRONMENT.md)
- [Every source file and its purpose](docs/FILE_MAP.md)
- [Moving source and data to another computer](docs/operations/TRANSFER.md)
- [Refactor scope and verification](docs/development/REFACTOR_REPORT.md)
- [Calling deployment requirements](docs/operations/voice-calls.md)

Old planning/status documents describe earlier development stages; they are not a current test report. The release report records what was actually checked for this package. Retained-chat migrations intentionally refuse destructive downgrades. Browser calling requires browser support, microphone permission and reachable media services; an entirely closed browser cannot promise app-style incoming calls.
