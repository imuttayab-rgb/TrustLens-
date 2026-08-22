# TrustLens

**AI-Powered Seller Trust Verification System for Online Marketplaces**

Final Year Project — School of Software Engineering, Minhaj University Lahore
Haseeb Ur Rehman (2022F-mulbsswe-043) · Muhammad Muttayab (2022F-mulbsswe-012)
Supervisor: Mam Misbha

---

## What it does

TrustLens verifies whether an online marketplace seller is genuine or fake and publishes a single
**explainable Trust Score (0–100)** with a risk level and the reasons behind it, so buyers can judge a
seller before paying.

It combines seven independent signal families — identity (CNIC OCR + face match), phone, email, device,
network/VPN, account behaviour, and AI listing analysis — into one score, and exposes that score to
marketplaces through a public REST API.

## Stack

| Layer    | Technology                                                                                                                                                    |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend | Next.js (React) · Tailwind CSS · TypeScript → **Vercel** (planned)                                                                                            |
| Backend  | Python · FastAPI · SQLAlchemy · Alembic → **Fly.io** (planned)                                                                                                |
| Worker   | ARQ over Redis (OCR, face match, LLM, scoring) → **Fly.io** (planned)                                                                                         |
| Database | PostgreSQL · Redis (cache + queue)                                                                                                                            |
| AI       | OpenAI / Claude API · RapidOCR + InsightFace on ONNX runtime, with EasyOCR + DeepFace kept behind a setting for benchmarking · custom scam-listing classifier |
| Tooling  | pnpm · Turborepo · uv · Docker · Postman                                                                                                                      |

Nothing is deployed yet — the hosting column is the decision recorded in
[`docs/20-go-live-plan.md`](docs/20-go-live-plan.md), not a live system.

## Status

**Built and running locally.** 330 Python tests pass, `mypy`/`ruff`/`tsc`/`eslint` are clean, the
architecture contracts hold, and the API serves 50 paths against 40 migrated tables.

End to end today: register → verify the email → sign in → create a seller profile → complete the
identity, phone, email and device checks → read an explainable Trust Score with its per-signal
breakdown and ranked improvements → appeal it → have a reviewer decide and trigger a recompute.
Buyers can open a seller's public page; partner marketplaces can read a signed score through the
API-key-authenticated public API.

**Not done yet:** the trained scam classifier, most of the admin panel, and deployment — there is
no public URL. Real CNIC and face images have never been tested, so there are no accuracy numbers.

The ordered list of remaining work is [`REMAINING.md`](REMAINING.md); the history, with the
defects found along the way, is [`TASKS.md`](TASKS.md).

## Documentation

| Start here                                                   |                                                                 |
| ------------------------------------------------------------ | --------------------------------------------------------------- |
| [ARCHITECTURE.md](ARCHITECTURE.md)                           | 5-minute overview and the three decisions that shape everything |
| [docs/README.md](docs/README.md)                             | Full documentation index (20 documents + 7 ADRs)                |
| [docs/01-project-overview.md](docs/01-project-overview.md)   | Requirements traced to the proposal, assumptions, build order   |
| [docs/11-development-setup.md](docs/11-development-setup.md) | How to install, run, migrate, seed and test                     |
| [DEPLOYMENT.md](DEPLOYMENT.md)                               | Click-by-click deployment guide                                 |

## Quick start

**Production mode** — the whole product in containers, the way it is handed over:

```bash
make prod-init     # first run: creates .env.production with real secrets
make prod-up       # build and start everything
make prod-check    # verify it is actually serving
```

Windows: double-click **`prod-start.bat`**. Day-to-day operation is in
[`RUNBOOK.md`](RUNBOOK.md).

**Development mode** — hot reload, run from source.

Windows, one click: run **`start.bat`** (and `stop.bat` to shut it down).

Everywhere else:

```bash
make setup         # deps, .env, docker services, migrations, seed data
make dev           # web :3000 · admin :3001 · api :8000 · worker
make dev-offline   # same, with USE_FAKE_AI=true — no API keys or internet needed
```

Seeded demo accounts are listed in [`CREDENTIALS.dev.md`](CREDENTIALS.dev.md).

## Licence

Academic project, not licensed for commercial use. Note that the pretrained face-recognition
weights it depends on carry non-commercial research licences, which academic FYP use permits.
