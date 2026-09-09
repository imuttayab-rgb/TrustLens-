# Local development credentials

Everything here belongs to the **demo seed**, which runs only in development.
`start.bat` creates it all automatically.

> ⚠️ **These accounts do not exist in production, by design.** Deployment seeds
> _reference_ data only (roles, permissions, signals, scoring weights) — never
> the demo seed. Fake sellers with fake scores must never reach a real database.
> Nothing in this file is a secret worth protecting: it is all in
> `packages/py/trustlens-db/src/trustlens/db/seed/demo.py` in plain sight.

---

## Where things run

| What            | URL                          | Notes                                         |
| --------------- | ---------------------------- | --------------------------------------------- |
| Seller site     | http://localhost:3000        | Register, verify, upload, see your score      |
| Browse listings | http://localhost:3000/browse | Public catalog: search, categories, favorites |
| Admin panel     | http://localhost:3001        | Review queue, appeals, partners               |
| API docs        | http://localhost:8000/docs   | Swagger, every endpoint                       |
| **Email inbox** | http://localhost:8025        | **Mailpit — all outgoing mail lands here**    |
| File storage    | http://localhost:9001        | MinIO console                                 |

---

## Logins

### Staff — use these on the **admin panel** (:3001)

| Email                    | Password             |
| ------------------------ | -------------------- |
| `admin@trustlens.dev`    | `Admin!Passw0rd123`  |
| `reviewer@trustlens.dev` | `Review!Passw0rd123` |

A **reviewer** can work the queue and resolve appeals but **cannot override a
score** — that is admin-only, on purpose. Worth showing in the demo: it is a
real separation of duties, not a missing feature.

### Sellers — use these on the **seller site** (:3000)

All three share the password `Seller!Passw0rd123`.

| Email                       | Business       | Public page              | Risk band          |
| --------------------------- | -------------- | ------------------------ | ------------------ |
| `seller.high@trustlens.dev` | Ayesha Traders | `/seller/ayesha-traders` | 🟢 **LOW risk**    |
| `seller.mid@trustlens.dev`  | Bilal Motors   | `/seller/bilal-motors`   | 🟡 **MEDIUM risk** |
| `seller.low@trustlens.dev`  | Quick Deals PK | `/seller/quick-deals-pk` | 🔴 **HIGH risk**   |

> ### ⚠️ Read the names backwards
>
> `seller.**high**` is the **most trustworthy** seller — high _trust_, therefore
> **low risk**. `seller.**low**` is the scammer profile.
>
> The email says trust; the badge says risk. They are opposites. Do not open
> `seller.low` in the demo expecting a good score.

### Buyer

| Email                 | Password            |
| --------------------- | ------------------- |
| `buyer@trustlens.dev` | `Buyer!Passw0rd123` |

A buyer can look up sellers but has no seller profile of their own.

---

## Infrastructure

Local containers only. Fine to keep in git precisely because they are
unreachable from anywhere but this machine.

| Service  | User         | Password        |
| -------- | ------------ | --------------- |
| Postgres | `trustlens`  | `trustlens`     |
| MinIO    | `minioadmin` | `minioadmin`    |
| Redis    | —            | no auth locally |

```bash
# psql into the dev database
docker exec -it trustlens-postgres psql -U trustlens -d trustlens
```

---

## Things that will confuse you once

**Verification emails do not go to a real inbox.** Register a new account and
the confirmation link lands in **Mailpit at http://localhost:8025**. Nothing is
broken; that is the local mail server. Without clicking that link, login fails
with `EMAIL_NOT_VERIFIED` — which is correct behaviour.

**Phone OTPs are printed, not sent.** With `USE_FAKE_AI=true` and the mock SMS
driver, the code appears in the **worker window**, not on a phone.

**The AI is fake by default.** `USE_FAKE_AI=true` means OCR and face matching
return deterministic made-up results, so the whole system runs offline with no
API keys. Real engines are `OCR_ENGINE=rapidocr` and `FACE_ENGINE=insightface`,
which need the `onnx` extra installed.

**Favorites live under the seller dashboard, even for the buyer account.**
`buyer@trustlens.dev` has no seller profile, but `RequireSession` only checks
for a signed-in user, not a seller one - so it can still reach
`/dashboard/favorites` after saving a listing from `/browse`. Its other nav
items ("Selling", "Score") are seller-only and will not work for it; that gap
predates this feature and is not fixed here.

---

## Resetting

```bash
stop.bat                      # stop everything, keep the data
start.bat                     # start again; seeds are idempotent

# start completely fresh (deletes the database):
docker compose -f docker/compose/docker-compose.dev.yml down -v
start.bat
```
