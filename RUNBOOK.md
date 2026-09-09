# TrustLens — Runbook

**For whoever is running this system.** Start it, stop it, fix it, and know what
to do when something breaks. No prior knowledge of the codebase assumed.

Written for the handover to Haseeb and Muttayab (P11-02).

---

## 1. Start it

### Windows

Double-click **`prod-start.bat`**.

First run takes 10–20 minutes — it builds four Docker images. Every run after
that takes about 30 seconds.

### Anything else

```bash
make prod-init     # first time only: creates .env.production with real secrets
make prod-up       # build and start everything
make prod-check    # confirm it is actually serving
```

### What you get

|                 |                              |
| --------------- | ---------------------------- |
| Seller app      | http://localhost:3000        |
| Browse listings | http://localhost:3000/browse |
| Admin panel     | http://localhost:3001        |
| API docs        | http://localhost:8000/docs   |
| Email inbox     | http://localhost:8025        |
| Storage console | http://localhost:9001        |

Demo logins are in [`CREDENTIALS.dev.md`](CREDENTIALS.dev.md).

**There is no real email in this setup.** Every message — verification links,
OTPs, appeal notifications — lands in the inbox at :8025. That is deliberate:
nothing leaves the machine, and a demo works with no accounts anywhere.

---

## 2. Stop it

```bash
make prod-down          # stops everything, keeps all data
make prod-nuke          # stops everything and DELETES ALL DATA
```

On Windows: **`prod-stop.bat`**.

`prod-nuke` is irreversible. Take a backup first (§6).

---

## 3. Is it working?

```bash
make prod-check
```

Checks what a user would actually experience, not just whether containers
exist. Expect **7 passing checks** plus a worker line.

```bash
make prod-security     # 16 more: PII, headers, auth, brute force, secrets
```

| Endpoint             | Means                                  |
| -------------------- | -------------------------------------- |
| `GET /health/live`   | the API process is up                  |
| `GET /health/ready`  | it can reach Postgres and Redis        |
| `GET /health/worker` | **the worker is still consuming jobs** |

The third one matters most, and it is the one people forget to build. A worker
can be running, connected, and doing nothing — every normal check says
"healthy", and the only symptom is verifications that never finish. If
`/health/worker` says `stale`, that is the case. Restart it:

```bash
make prod-restart
```

On a freshly started stack it will say `unknown` — the worker has not run a job
yet. That is not a fault. Register a user and check again.

---

## 4. Read the logs

```bash
make prod-logs                                          # everything, live
make prod-logs 2>&1 | grep -i error                     # just the errors
docker compose -f docker/compose/docker-compose.prod.yml \
  --env-file .env.production logs -f worker             # one service
```

Logs are structured JSON with a `request_id` on every line. A user reporting
"my verification is stuck" gives you a request id from the error page; grep for
it and you get the whole story, HTTP request and background job together.

---

## 5. Common problems

### "Port is already in use"

Something else is on 3000, 3001 or 8000. Change the port in `.env.production`
(`WEB_PORT`, `ADMIN_PORT`, `API_PORT`) and run `make prod-up` again.

If it is a leftover TrustLens process rather than another app:

```bash
netstat -ano | grep ":8000 "     # note the PID in the last column
taskkill //PID <pid> //F         # Windows
```

### The site loads but every API call fails

Almost always CORS or a wrong URL. Check that `NEXT_PUBLIC_API_BASE_URL` and
`SECURITY_CORS_ORIGINS` in `.env.production` agree with the address you are
actually using.

**`NEXT_PUBLIC_*` values are compiled into the browser bundle.** Changing one
needs `make prod-build`, not a restart. This catches everyone exactly once.

### Verification never completes

The worker is not consuming. Check `/health/worker`, then `make prod-restart`.

### "Job queue is backing up"

```bash
docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production \
  exec redis redis-cli -n 1 LLEN arq:queue
```

A number that climbs and never falls means the worker is stuck or dead. Restart
it. The queue is persisted, so nothing is lost — jobs resume where they
stopped.

### A seller cannot sign in

1. Confirm the account exists and is verified — admin panel, or query the
   database (§8).
2. Check the email actually arrived: http://localhost:8025.
3. Reset the password (§8).

### Everything is slow on first request

Cold start. Containers were idle and the first request wakes them. Normal.
Before a demo, open the site once so the examiner's first click is not the
wake-up call.

---

## 6. Backups

```bash
bash scripts/db-backup.sh                # take one, into backups/
bash scripts/db-restore.sh --verify      # PROVE the newest one restores
```

`--verify` restores into a throwaway database, counts what came back, and drops
it. Nothing live is touched. **Run it monthly.** An untested backup is a guess.

Verified working on 22 August 2026: 41 tables and 9 user rows recovered.

To actually restore over a live database:

```bash
bash scripts/db-restore.sh --into trustlens backups/trustlens-prod-XXXX.dump
```

It asks you to type the database name, takes a safety backup of what is there
now, and only then replaces it.

---

## 7. Roll back a bad deploy

Everything is a container, so rollback is going back to the previous code:

```bash
git log --oneline -5
git checkout <the commit that worked>
make prod-up
```

**If a migration ran, code alone is not enough** — the database schema moved
forward. Restore the backup from before the deploy (§6), then check out the old
code.

This is why `scripts/db-backup.sh` should run _before_ any deploy that includes
a migration.

---

## 8. Database access

```bash
docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production \
  exec postgres psql -U trustlens -d trustlens
```

Useful queries:

```sql
-- Who is registered?
SELECT email, role, is_email_verified, created_at FROM users ORDER BY created_at DESC LIMIT 20;

-- Sellers and their current scores
SELECT sp.handle, ts.score, ts.risk_level, ts.computed_at
FROM seller_profiles sp
LEFT JOIN trust_scores ts ON ts.id = sp.current_trust_score_id
ORDER BY ts.score NULLS LAST;

-- Jobs that died
SELECT job_name, status, attempts, error, created_at
FROM job_runs WHERE status = 'DEAD' ORDER BY created_at DESC LIMIT 20;

-- Appeals waiting on a reviewer
SELECT id, seller_id, status, category, created_at FROM appeals WHERE status = 'OPEN';
```

**Reset someone's password** — there is no admin "reset password" screen yet, so
do it through the app's own flow: use "forgot password" on the login page and
read the email at :8025. That keeps the password hashing in one place, which is
where it belongs.

---

## 9. Move a piece to a hosted service

Every backing service is reached only through a URL in the env file, so moving
one is an edit and a restart — no code change, no rebuild.

**For the frontends on Vercel and the database on Neon** there is a dedicated
compose file, because that split needs more than a URL change:

```bash
make hosted-init       # creates .env.hosted
# fill in the Neon URLs and the Vercel addresses
make hosted-migrate    # create the schema on Neon
make hosted-up         # start api + worker against it
```

Step by step, with the traps: **[`ACCOUNTS.md`](ACCOUNTS.md) section 4**.

**Why a separate file rather than `--scale postgres=0`.** The production compose
has `depends_on: postgres: service_healthy` on api, worker and migrate. Scaling
postgres to zero does not remove that condition — it makes all three wait
forever for a container that will never start.

For the pieces that _can_ be swapped in place:

| Piece   | Change in `.env.production`                | Then                |
| ------- | ------------------------------------------ | ------------------- |
| Redis   | `REDIS_URL`, `REDIS_QUEUE_URL`             | `--scale redis=0`   |
| Storage | `STORAGE_ENDPOINT_URL` + the two keys      | `--scale minio=0`   |
| Email   | `EMAIL_PROVIDER=resend` + `RESEND_API_KEY` | `--scale mailpit=0` |

Copy-paste values for Neon, Upstash, R2 and Resend are at the bottom of
`.env.production.example`.

**Three traps, all of which fail silently:**

- **`NEXT_PUBLIC_*` is compiled into the browser bundle** — changing one needs a
  rebuild, not a restart.
- **`SECURITY_TRUSTED_HOSTS` must list every hostname the API answers on**, or
  it returns 400 to everything while every health check reports healthy.
- **`SECURITY_CORS_ORIGINS` must list the browser's origin**, or the browser
  blocks the call and the API log shows nothing wrong.

**Neon's free tier sleeps after 5 minutes idle** (first request then takes 3–5
seconds) and **closes idle connections** — which is why `.env.hosted.example`
sets a small, frequently-recycled pool.

---

## 10. Turning on the real AI

`USE_FAKE_AI=true` is the default and every journey works with it — no API
keys, no internet. Change it only when you want real OCR and face matching.

```
USE_FAKE_AI=false
```

The models are already baked into the worker image, so nothing downloads at
boot. Expect ~2 seconds per document on a normal laptop and more on a small
server; identity verification is asynchronous and polled, so this is slow, not
broken.

**Do not turn on the trained scam classifier for real scoring yet.** Read
[`apps/ml/README.md`](apps/ml/README.md) first. It scores F1 0.906 on its
training corpora and catches 1 scam in 7 on Pakistani marketplace ads, and its
output feeds a seller's trust score. It needs the in-domain corpus (P7-02) first.

---

## 11. Monitoring

Structured JSON logs are always on, and are a complete setup for a laptop.

For alerts, set `SENTRY_DSN` in `.env.production` (Sentry's free tier is 5,000
events/month). Errors are scrubbed before they leave the machine — anything
whose key looks like a password, token, CNIC, OTP or selfie is redacted, and
request bodies are never sent. This system holds biometric data; error
reporting must not be the thing that leaks it.

For uptime, point any free monitor (UptimeRobot, BetterStack) at:

- `GET /health/ready` — is the API serving
- `GET /health/worker` — is the worker consuming

Both return 503 when unhealthy, so a monitor will actually fire.

---

## 12. Who to ask

| Area                               | Where to look first                                              |
| ---------------------------------- | ---------------------------------------------------------------- |
| How the score is computed          | [`docs/08-trust-score-engine.md`](docs/08-trust-score-engine.md) |
| Why the architecture is like this  | [`ARCHITECTURE.md`](ARCHITECTURE.md), [`docs/adr/`](docs/adr/)   |
| What is built and what is not      | [`REMAINING.md`](REMAINING.md)                                   |
| The full history, defects included | [`TASKS.md`](TASKS.md)                                           |
| The ML model and why it is off     | [`apps/ml/README.md`](apps/ml/README.md)                         |
| Credentials for demo accounts      | [`CREDENTIALS.dev.md`](CREDENTIALS.dev.md)                       |

---

_Last verified 22 August 2026 against the production compose stack._
