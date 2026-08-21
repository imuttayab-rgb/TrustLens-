# 16 — Deployment Guide

Frontend → **Vercel** · Backend + worker + Postgres + Redis → **Railway** (both mandated by the proposal).

## 1. Environments

| Environment    | Frontend                | Backend                     | Database                   | Purpose                                  |
| -------------- | ----------------------- | --------------------------- | -------------------------- | ---------------------------------------- |
| **Local**      | `localhost:3000`        | `localhost:8000`            | Docker Postgres            | Development                              |
| **Preview**    | Vercel preview per PR   | Railway PR environment      | Ephemeral, seeded          | Review a PR as a running app             |
| **Staging**    | `staging.trustlens.app` | `api-staging.trustlens.app` | Managed, separate instance | Pre-release verification, demo rehearsal |
| **Production** | `trustlens.app`         | `api.trustlens.app`         | Managed + PITR backups     | Live                                     |

Preview environments are worth the setup cost on a 2-person team: a supervisor can click a PR link and
see the feature running, which replaces a scheduling round-trip with a URL.

## 2. Backend services

> **Superseded in part, August 2026.** This section was written against Railway. The host
> decision moved to **Fly.io** in [`docs/20-go-live-plan.md`](20-go-live-plan.md), and the
> worker image was rebuilt on ONNX runtimes. Neither has been deployed yet (P9-03), so the
> table below describes the shape rather than a live system. The Dockerfile paths and the
> image sizes are current; the platform names are not.

| Service    | Build                      | Start                                                                    | Scaling                                 |
| ---------- | -------------------------- | ------------------------------------------------------------------------ | --------------------------------------- |
| `api`      | `docker/api.Dockerfile`    | `uvicorn trustlens_api.main:app --host 0.0.0.0 --port $PORT --workers 2` | 1–3 replicas, CPU-triggered             |
| `worker`   | `docker/worker.Dockerfile` | `arq trustlens_worker.main.WorkerSettings`                               | 1–2 replicas, queue-depth-triggered     |
| `postgres` | Managed (Neon)             | —                                                                        | Vertical; PITR enabled                  |
| `redis`    | Managed (Upstash)          | —                                                                        | Vertical; AOF persistence for the queue |

Two images, not one: the API image excludes the ML stack entirely and is ~200 MB; the worker
image carries ONNX runtime plus baked model weights at **1.16 GB measured** (it was ~2.5 GB
before the swap away from PyTorch and TensorFlow). Sharing one image would make every API
deploy slow and every API replica carry a gigabyte of unused ML dependencies.

**Sizing is decided by RAM, not image size.** The worker peaks at **323 MB** with both
engines resident, so it needs a 512 MB instance — the one component that does not fit a free
tier.

Health checks: `GET /health/live` (process alive — no dependency checks, so a Redis blip doesn't trigger
a restart loop) and `GET /health/ready` (DB + Redis reachable — gates traffic).

## 3. Vercel

- Root directory `apps/web`, framework preset Next.js, build `pnpm turbo run build --filter=web`.
- `turbo-ignore` in the ignored-build step: a PR touching only `apps/api` skips the frontend build.
- Env vars per environment; `NEXT_PUBLIC_*` values are baked at build time — changing one requires a
  redeploy, not just a restart. This trips people up regularly.
- Region chosen closest to the Railway backend to minimise server-component fetch latency.
- Headers/redirects from `vercel.json` at the repo root (not yet created — P9-02).

## 4. Pipelines

```
PR opened
  └─ CI: lint → typecheck → arch → unit → integration → build → codegen-drift → migration-check → security
     └─ Vercel preview + Railway PR environment
        └─ E2E against the preview (PRs targeting main)

Merge to develop
  └─ CI → migrate staging → deploy api + worker → deploy web → smoke tests

Tag v*.*.* on main
  └─ CI → manual approval → backup production DB
        → migrate → deploy api (rolling) → deploy worker → deploy web
        → smoke tests → announce
```

## 5. Migrations

Migrations run as a **release step**, never at application startup.

```bash
railway run --service api alembic upgrade head
```

Two API replicas booting simultaneously would otherwise race to run the same migration; Alembic's
advisory lock prevents corruption but one replica would fail its health check and flap.

**Expand → migrate → contract** for every schema change, so the previous app version keeps working
during a rolling deploy:

| Phase    | Release | Example: renaming `score` → `trust_score` |
| -------- | ------- | ----------------------------------------- |
| Expand   | N       | Add `trust_score`, backfill, dual-write   |
| Migrate  | N+1     | Read from `trust_score`                   |
| Contract | N+2     | Drop `score`                              |

Never in a single deploy: dropping or renaming a column that the currently-running version reads, or
adding a `NOT NULL` column without a default.

Long backfills are separate migrations run as one-off jobs, so a slow data change never blocks a schema
change or a deploy.

## 6. Rollback

| Failure                          | Action                                                                                                  |
| -------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Frontend bug                     | Vercel "Promote to production" on the previous deployment (instant)                                     |
| Backend bug, no schema change    | Redeploy the previous image tag                                                                         |
| Backend bug with a schema change | Redeploy the previous image; the expand/contract rule guarantees it still runs against the new schema   |
| Bad migration                    | `alembic downgrade -1` — only if the down path was tested; otherwise restore from the pre-deploy backup |
| Data corruption                  | PITR restore to the timestamp before the incident                                                       |

Every deploy is preceded by an automated database backup, and every migration's `downgrade()` is
exercised in CI (`upgrade head → downgrade base → upgrade head`). An untested `downgrade()` is not a
rollback plan.

## 7. Zero-downtime checklist

- Rolling replica replacement with health-gated traffic.
- `SIGTERM` handling: API stops accepting connections and drains in-flight requests (30 s grace).
- Worker `SIGTERM`: finishes the current job, stops pulling; jobs are idempotent so a killed job is
  safely retried.
- Backward-compatible API changes only within a version.
- Cache keys namespaced by app version where the payload shape changed, so an old replica cannot read a
  new-shaped cache entry.

## 8. Configuration & secrets

Secrets live in the Railway/Vercel dashboards and GitHub Actions secrets — never in the repository, never
in an image. Startup validation ([12](12-environment-variables.md)) fails the boot on anything missing,
so a misconfigured deploy fails health checks and is rolled back automatically instead of running in a
half-broken state.

Rotation: JWT keys rotate with an overlap window (verify with both, sign with the new); encryption keys
rotate by key id with a background re-encrypt; API keys rotate client-side with two active keys.

## 9. Observability in production

| Concern | Tool                                                              |
| ------- | ----------------------------------------------------------------- |
| Logs    | Railway log stream (JSON), searchable by `request_id`             |
| Errors  | Sentry, with releases tagged by git SHA and source maps uploaded  |
| Metrics | `/metrics` scraped, or Railway metrics                            |
| Traces  | OpenTelemetry → OTLP collector (optional)                         |
| Uptime  | External monitor on `/health/ready` and the public score endpoint |

Alerts that matter: error rate > 1% for 5 min · p95 latency > 1 s · queue depth > 100 · dead-letter jobs

> 0 · DB connections > 80% of max · disk > 80% · certificate expiry < 14 days · AI spend > 80% of the
> monthly budget.

## 10. Backups & DR

| What           | Method                         | Retention | Verified                                                       |
| -------------- | ------------------------------ | --------- | -------------------------------------------------------------- |
| Postgres       | Railway automated daily + PITR | 30 days   | Monthly restore rehearsal into staging                         |
| Object storage | Bucket versioning + lifecycle  | 30 days   | Quarterly                                                      |
| Redis          | Not backed up                  | —         | By design — it is a cache and a queue; a rebuild is acceptable |
| Secrets        | Offline encrypted copy         | —         | On rotation                                                    |

Targets: RPO ≤ 1 hour (PITR), RTO ≤ 4 hours. A restore that has never been rehearsed is a hypothesis.

## 11. Domains & DNS

| Host                         | Points to                                |
| ---------------------------- | ---------------------------------------- |
| `trustlens.app`, `www`       | Vercel                                   |
| `api.trustlens.app`          | Railway `api`                            |
| `media.trustlens.app`        | Object storage (separate origin, §15 §6) |
| `staging.*`, `api-staging.*` | Staging equivalents                      |

Certificates are automatic on both platforms; CAA records restrict issuance.

## 12. Cost control (an FYP constraint, not an afterthought)

| Lever                                        | Effect                                                                                  |
| -------------------------------------------- | --------------------------------------------------------------------------------------- |
| `AI_MONTHLY_BUDGET_USD`                      | Degrades to classifier-only analysis when exceeded, rather than failing or overspending |
| Redis score cache (300 s)                    | Collapses partner polling to ~1 DB read per seller per 5 minutes                        |
| Listing analysis rate limit (10/day/seller)  | Caps the dominant LLM cost driver                                                       |
| `USE_FAKE_AI` in staging/preview/test        | Zero AI spend outside production                                                        |
| Worker scale-to-zero when the queue is empty | Idle cost near zero                                                                     |
| `max_tries` on every job                     | A failing job cannot retry into a large bill                                            |

## 13. Go-live checklist

- [ ] Production env vars set and validated; `DEBUG=false`
- [ ] Migrations applied; seed reference data present (`roles`, `permissions`, `signal_definitions`,
      scoring model v1 + weights)
- [ ] Admin account created with MFA enrolled; demo/seed accounts removed
- [ ] Health checks green; smoke tests passing
- [ ] Custom domains + TLS + HSTS active
- [ ] Security checklist ([15 §13](15-security.md)) complete
- [ ] Backups verified by an actual restore
- [ ] Monitoring and alerts firing to a channel someone reads
- [ ] Public API docs and Postman collection published
- [ ] Rate limits verified under a real burst
- [ ] Rollback rehearsed
