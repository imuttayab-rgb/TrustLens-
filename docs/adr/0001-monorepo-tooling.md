# ADR-0001: pnpm + Turborepo + uv for a polyglot monorepo

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Haseeb Ur Rehman, Muhammad Muttayab

## Context

The proposal mandates Next.js/React (TypeScript) for the frontend and Python/FastAPI for the backend.
A monorepo is wanted so that a change to an API response shape and the frontend that consumes it is one
commit, one PR, one CI run. Most monorepo tooling assumes a single language.

## Decision

Two workspace managers, one task vocabulary:

- **pnpm workspaces** for `apps/web` and `packages/*` (TypeScript)
- **uv workspaces** for `apps/api`, `apps/worker`, `apps/ml`, `packages/py/*` (Python), one lockfile
- **Turborepo** for the JS task graph and build caching
- **A root `Makefile`** as the single cross-language entry point: `make dev`, `make test`, `make migrate`

## Alternatives considered

| Option | Why rejected |
|---|---|
| **Nx** | Genuinely polyglot, but a large concept surface (executors, generators, project graph config) for a 2-person team on a 2-semester timeline. The learning cost would come out of feature time |
| **Bazel** | Correct answer for large polyglot monorepos; wildly disproportionate here. Nobody would finish the BUILD files |
| **Polyrepo (separate frontend/backend repos)** | Forfeits the main benefit: atomic cross-stack changes. An API change and its frontend update would be two PRs in two repos with no CI that sees both |
| **Git submodules** | All the coordination cost of a polyrepo plus a notoriously error-prone tool |
| **Single-language rewrite** | Would violate the proposal's mandated stack |
| **Poetry instead of uv** | Works, but is markedly slower to resolve and install; uv's workspace support and speed matter in CI where the ML dependency set is large |

## Consequences

**Positive**
- Atomic cross-stack changes; one CI run sees both sides.
- Shared config (ESLint, tsconfig, Ruff, mypy) applied once.
- Turborepo caching keeps CI fast as the repo grows.
- `make` hides the two-toolchain reality behind one vocabulary.

**Negative / accepted costs**
- Two package managers and two lockfiles to keep healthy.
- Contributors need both Node and Python toolchains installed.
- Turborepo caches only the JS side; Python task caching is manual (mitigated by pytest's own caching and
  CI path filters).

**Revisit if:** the team grows past ~6 developers, or a third language enters the repo — at that point
Nx's polyglot project graph starts to pay for its complexity.
