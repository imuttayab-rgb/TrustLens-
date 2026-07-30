# Architecture Decision Records

An ADR captures a decision that was **contested or non-obvious**, along with the alternatives that were
rejected and why. Obvious decisions don't need one.

Format: Context → Decision → Alternatives considered → Consequences (good and bad).
Status: `Proposed` · `Accepted` · `Superseded by ADR-XXXX` · `Deprecated`.
ADRs are **immutable once accepted** — a changed mind means a new ADR that supersedes the old one, so
the reasoning history stays intact. That history is what a viva examines.

| # | Title | Status |
|---|---|---|
| [0001](0001-monorepo-tooling.md) | pnpm + Turborepo + uv for a polyglot monorepo | Accepted |
| [0002](0002-deterministic-scoring.md) | Deterministic rule engine scores; AI provides evidence | Accepted |
| [0003](0003-async-ai-pipeline.md) | AI runs in a separate worker process, not in the API | Accepted |
| [0004](0004-clean-architecture-ports.md) | Framework-free domain package with ports and adapters | Accepted |
| [0005](0005-openapi-as-contract.md) | OpenAPI is the single source of truth for the frontend contract | Accepted |
| [0006](0006-jwt-refresh-rotation.md) | JWT access tokens + rotating refresh cookies with reuse detection | Accepted |
| [0007](0007-versioned-scoring-models.md) | Scoring weights live in the database and are versioned | Accepted |

## Template

```markdown
# ADR-XXXX: <title>

- **Status:** Proposed | Accepted | Superseded by ADR-YYYY
- **Date:** YYYY-MM-DD
- **Deciders:** <names>

## Context
What forces are at play? What constraint or requirement triggered this?

## Decision
What we are doing, stated plainly.

## Alternatives considered
| Option | Why rejected |

## Consequences
**Positive:** …
**Negative / accepted costs:** …
**Revisit if:** <the concrete trigger that would reopen this>
```
