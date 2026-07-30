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

| Layer | Technology |
|---|---|
| Frontend | Next.js (React) · Tailwind CSS · TypeScript → **Vercel** |
| Backend | Python · FastAPI · SQLAlchemy · Alembic → **Railway** |
| Worker | ARQ over Redis (OCR, face match, LLM, scoring) → **Railway** |
| Database | PostgreSQL · Redis (cache + queue) |
| AI | OpenAI / Claude API · OpenCV · EasyOCR · DeepFace · custom scam-listing classifier |
| Tooling | pnpm · Turborepo · uv · Docker · Postman · Figma |

## Status

**Design phase.** The complete architecture is specified in [`docs/`](docs/README.md); implementation has
not started. Start with [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Documentation

| Start here | |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 5-minute overview and the three decisions that shape everything |
| [docs/README.md](docs/README.md) | Full documentation index (19 documents + ADRs) |
| [docs/01-project-overview.md](docs/01-project-overview.md) | Requirements traced to the proposal, assumptions, build order |
| [docs/11-development-setup.md](docs/11-development-setup.md) | How to run it once the scaffold exists |

## Quick start (once scaffolded)

```bash
make setup     # deps, .env, docker services, migrations, seed data
make dev       # web :3000 · api :8000 · worker
make dev-offline   # same, with USE_FAKE_AI=true — no API keys or internet needed
```

## Licence

Academic project. See [LICENSE](LICENSE).
