# 13 — Coding Standards

## 1. Naming conventions

Full table in [10 §10](10-folder-structure.md#10-naming-conventions). Summary: `kebab-case` directories,
`PascalCase` React components and Python classes, `snake_case` Python modules and database identifiers,
`camelCase` JSON on the wire, `SCREAMING_SNAKE_CASE` constants and env vars.

Additional rules:

- **No `I` prefix on interfaces/protocols.** `OcrEngine`, not `IOcrEngine` — Hungarian notation for
  abstractions leaks implementation vocabulary into the domain.
- **No abbreviations** except universally understood ones (`id`, `url`, `api`, `db`, `ocr`, `cnic`).
  `calculateTrustScore`, never `calcTS`.
- **Booleans read as assertions**: `isVerified`, `hasActiveAppeal`, `canOverrideScore`.
- **Domain vocabulary is fixed and shared.** *Signal*, *Trust Score*, *Risk Level*, *Appeal*,
  *Review Case*, *Scoring Model*, *Marketplace*. The same word means the same thing in the database, the
  API, the UI, and the FYP report. Renaming a concept means renaming it everywhere, in one PR.

## 2. Python standards

| Tool | Purpose | Config |
|---|---|---|
| **Ruff** | Lint + import sorting (replaces flake8, isort, pyupgrade, bandit-lite) | Root `pyproject.toml` |
| **Black** | Formatting, line length 100 | Root `pyproject.toml` |
| **mypy** | `--strict` on `packages/py/*`, standard on `apps/*` | Root `pyproject.toml` |
| **import-linter** | Enforces the layering contracts in [02 §3](02-system-architecture.md) | `.importlinter` |
| **pytest** | Tests, `--cov`, `-x` locally | Root `pyproject.toml` |

Enabled Ruff rule groups: `E,W` (pycodestyle), `F` (pyflakes), `I` (isort), `N` (naming), `UP` (pyupgrade),
`B` (bugbear), `S` (bandit security), `A` (builtin shadowing), `C4`, `SIM`, `TCH`, `PTH`, `RUF`.
`S101` (assert) is disabled in test files only.

Conventions:

- **Type hints on every public function.** `mypy --strict` on `trustlens-core` means no untyped defs, no
  implicit `Any`, no untyped decorators.
- **`async def` all the way down** in request and job paths. One synchronous DB call blocks the event
  loop for every concurrent request on that worker. CPU-bound ML work runs in a thread/process executor,
  never inline in an async function.
- **No mutable default arguments**, ever (Ruff `B006`).
- **Dataclasses/Pydantic for data, classes for behaviour.** Anaemic classes with only getters are a
  smell; so are 12-parameter constructors.
- **Explicit exceptions.** Raise a typed `DomainError` subclass; never `raise Exception("...")`,
  never `except:` bare, never `except Exception: pass`.
- **No I/O in the domain layer.** No `requests`, no `open()`, no `datetime.now()`, no `uuid4()` inside
  `trustlens-core` — use the `Clock` and `IdGenerator` ports.
- **Docstrings** on public modules, classes, and non-obvious functions: what and *why*, not a restatement
  of the signature.
- Line length 100, double quotes, trailing commas.

## 3. TypeScript standards

| Tool | Purpose |
|---|---|
| **ESLint** (flat config) | `packages/config-eslint` — base, react, next, node presets |
| **Prettier** | Formatting — `configs/prettier.config.js` |
| **TypeScript** | `strict: true`, `noUncheckedIndexedAccess`, `noImplicitOverride`, `exactOptionalPropertyTypes` |
| **knip** | Dead code and unused dependency detection |

Key ESLint rules:

```
@typescript-eslint/no-explicit-any: error         # use unknown + narrowing
@typescript-eslint/no-floating-promises: error    # unawaited promises swallow errors
@typescript-eslint/consistent-type-imports: error
import/no-cycle: error
no-restricted-imports:                            # enforces the feature-slice boundary
  - "@/features/*/!(index)"                       # no deep imports into another feature
  - "@/app/*"                                     # nothing imports from the routing layer
react-hooks/exhaustive-deps: error
jsx-a11y/*: error                                 # accessibility is not optional here
```

Conventions:

- **No `any`.** Use `unknown` plus narrowing, or fix the type.
- **`type` for unions and object shapes; `interface` only for extendable contracts.**
- **Named exports** everywhere except Next.js pages/layouts, which must be default-exported.
- **Server vs client components:** default to a server component; add `'use client'` only when a browser
  API, event handler, or hook is genuinely needed, and add it as low in the tree as possible.
- **No business logic in `app/`.** Route files compose feature components and nothing else.
- **No inline `fetch`.** All HTTP goes through `packages/api-client` so auth, error normalisation, and
  types are applied uniformly.
- Never `localStorage` for tokens ([07 §3](07-authentication-authorization.md)).

## 4. Git workflow

**Trunk-based development with short-lived branches** — the right fit for a 2-person team where long-lived
branches mean painful merges and stale reviews.

```
main ──────●────────●────────●────────●──────►   protected; always deployable; tagged releases
            ╲      ╱ ╲      ╱
             ●────●   ●────●                     feat/… fix/… — 1–3 days each
```

| Branch | Purpose | Lifetime |
|---|---|---|
| `main` | Production. Protected. Deploys on tag | permanent |
| `develop` | Optional integration branch → staging. Use only if the team wants a staging gate | permanent |
| `feat/<issue>-<slug>` | New feature | ≤ 3 days |
| `fix/<issue>-<slug>` | Bug fix | ≤ 1 day |
| `chore/…`, `docs/…`, `refactor/…`, `test/…` | Maintenance | short |
| `hotfix/<slug>` | Production emergency; branches from `main`, merges to `main` | hours |

Rules: rebase onto `main` before opening a PR (linear history); **squash merge** so one PR = one commit on
`main`; delete the branch after merge; never force-push to `main` or `develop`.

`main` protection: PR required, ≥1 approval, all CI checks green, branch up to date, no force push, no
deletion.

## 5. Commit messages — Conventional Commits

```
<type>(<scope>): <subject>

[body — why, not what]

[footer — BREAKING CHANGE: …, Closes #42]
```

Types: `feat` · `fix` · `docs` · `style` · `refactor` · `perf` · `test` · `build` · `ci` · `chore` · `revert`

Scopes: `web` · `api` · `worker` · `ml` · `core` · `db` · `ai` · `ui` · `auth` · `scoring` · `verification`
· `listings` · `appeals` · `public-api` · `infra` · `docs`

```
feat(scoring): add hard cap when face match fails

A weighted sum alone let a seller who failed face match still score ~85
(LOW risk), which inverts the product's purpose. Critical signals now
clamp the final score via scoring_weights.hard_cap_on_fail.

Closes #87
```

Enforced by `commitlint` in a Husky `commit-msg` hook. Subject: imperative mood, ≤ 72 chars, no trailing
period. The **body explains why** — the diff already shows what.

## 6. Pull requests

Template (`.github/pull_request_template.md`):

```markdown
## What
## Why
## How
## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests where I/O or SQL changed
- [ ] Manually verified locally
## Checklist
- [ ] Migration reviewed line by line (if schema changed)
- [ ] `pnpm codegen` run (if the API contract changed)
- [ ] Docs updated (if behaviour or architecture changed)
- [ ] No secrets, no PII, no real CNIC images committed
- [ ] Env vars added to `.env.example` and docs/12
## Screenshots / API examples
## Related issues
```

Size limit: aim for < 400 changed lines. Beyond that, review quality collapses and the review becomes a
rubber stamp. Split by layer (migration → repository → use case → endpoint → UI).

## 7. Automated quality gates

### Husky hooks

| Hook | Runs | Why |
|---|---|---|
| `pre-commit` | `lint-staged` | Format + lint only what changed — fast |
| `commit-msg` | `commitlint` | Rejects a non-conventional message before it exists |
| `pre-push` | `make typecheck && make test-unit` | Catches the obvious break before CI does |

`pre-push` deliberately runs only *unit* tests — a pre-push hook that takes three minutes gets bypassed
with `--no-verify`, and a bypassed hook protects nothing.

### lint-staged

```js
// configs/lint-staged.config.js
module.exports = {
  '*.{ts,tsx,js,jsx}': ['prettier --write', 'eslint --fix --max-warnings=0'],
  '*.py':              ['ruff check --fix', 'ruff format', 'black'],
  '*.{json,yml,yaml,md}': ['prettier --write'],
  '*.md':              ['markdownlint --fix'],
  '*':                 ['gitleaks protect --staged --no-banner'],
};
```

The `gitleaks` entry on `*` is the most important line in this file: it blocks a committed API key at the
one moment when removing it is still cheap. Once a secret reaches `main`, it must be rotated regardless of
history rewriting.

### CI (`.github/workflows/ci.yml`)

Path-filtered so a docs change doesn't run the ML test suite:

1. **lint** — ruff, eslint, prettier check, markdownlint
2. **typecheck** — mypy, tsc
3. **arch** — import-linter contracts
4. **test-unit** — pytest + vitest, parallel
5. **test-integration** — testcontainers Postgres + Redis
6. **build** — turbo build + docker build
7. **codegen-drift** — regenerate the API client; fail if the diff is non-empty
8. **migration-check** — apply all migrations to an empty DB, then assert `alembic check` reports no
   pending autogenerate diff (models and migrations agree)
9. **security** — `pnpm audit`, `pip-audit`, gitleaks, Trivy on images
10. **e2e** — Playwright against a compose stack (on PRs to `main` only)

## 8. Documentation standards

- Every package and app has a `README.md`: purpose, how to run, how to test.
- **Architecture changes update `docs/` in the same PR.** Documentation that lags the code is worse than
  none, because it is confidently wrong.
- Non-obvious decisions get an [ADR](adr/README.md).
- Comments explain **why**, never what. `# increment i` is noise; `# EasyOCR returns tokens in reading
  order, but CNIC back pages are two-column, so re-sort by bbox x-position first` is the reason the next
  person doesn't "simplify" the code and break it.
- Every public API endpoint carries an OpenAPI `summary`, `description`, and example.

## 9. Definition of Done

A change is done when:
1. It meets the acceptance criteria on the issue.
2. Unit tests cover the new logic; integration tests cover new I/O.
3. `make ci` passes locally.
4. Types are strict; no new `any`, no new `# type: ignore` without a comment explaining it.
5. Docs and `.env.example` are updated if behaviour or config changed.
6. The migration is reviewed and reversible.
7. No secrets, no PII, and no real identity documents were committed.
8. A peer approved the PR.
