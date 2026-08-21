# 18 — Contribution Guide

Written for a two-person FYP team plus a supervisor, not for a large open-source project. The process is
as light as it can be while still producing a defensible codebase.

## 1. Before you start

1. Read [`ARCHITECTURE.md`](../ARCHITECTURE.md), [01](01-project-overview.md), [02](02-system-architecture.md),
   and the doc for the layer you are touching.
2. Set up locally: [11 — Development Setup](11-development-setup.md).
3. Skim [13 — Coding Standards](13-coding-standards.md).

## 2. Workflow

```
Issue ──► branch ──► commits ──► PR ──► review ──► squash merge ──► delete branch
```

1. **Every change starts with an issue.** Even a one-liner. The issue is what the FYP report cites.
2. `git switch -c feat/42-cnic-ocr-pipeline` off an up-to-date `main`.
3. Commit in Conventional Commits format ([13 §5](13-coding-standards.md)).
4. Rebase onto `main` before opening the PR.
5. `make ci` locally — CI should confirm, not discover.
6. Open the PR with the template filled in; link the issue.
7. Get one approval; squash merge; delete the branch.

## 3. Division of work

With two developers, the highest risk is both people editing the same files and neither understanding the
other's half. Mitigations:

- **Split by vertical slice, not by layer.** "Haseeb builds phone OTP end to end (migration → repository →
  use case → endpoint → UI)" beats "Haseeb does all backend, Muttayab does all frontend" — the latter
  creates a permanent integration cliff and a bus factor of one on each half.
- **Rotate slices** so both members touch backend, frontend, and AI work. The FYP viva can ask either
  member about any part.
- **Agree contracts first.** For a cross-cutting feature, agree the API schema before implementation; the
  OpenAPI doc and the generated client then keep both halves honest.
- **Daily 10-minute sync**: what's merged, what's in flight, what's blocked.

## 4. Review guidelines

The reviewer checks, in priority order:

1. **Correctness** — does it do what the issue asked? Are edge cases handled?
2. **Security** — authz on every new endpoint, validated input, no PII in logs or responses,
   no secret committed.
3. **Architecture** — does it respect the layering ([02 §3](02-system-architecture.md))? Is business
   logic in the domain rather than in a router or a component?
4. **Tests** — do they cover the new behaviour, including the failure branches?
5. **Naming and clarity** — will this read well in six weeks?
6. **Docs** — are `docs/` and `.env.example` updated if behaviour or config changed?

Review etiquette: comment on the code, never the person; distinguish blocking issues from suggestions
(prefix non-blocking ones with `nit:`); explain _why_, and suggest a concrete alternative; approve when
it is good enough to merge, not when it is what you would have written.

Turnaround target: 24 hours. A PR that sits for three days is a merge conflict in waiting.

## 5. What needs extra scrutiny

| Change                             | Extra requirement                                                                             |
| ---------------------------------- | --------------------------------------------------------------------------------------------- |
| Database migration                 | Read line by line; confirm `downgrade()` works; confirm expand/contract compliance            |
| Scoring weights or thresholds      | Run `POST /admin/scoring-models/{id}/simulate` and attach the distribution delta to the PR    |
| Anything touching CNIC/selfie data | Explicit security review against [15](15-security.md); confirm no new logging of PII          |
| New public API endpoint or field   | Confirm no PII; confirm the OpenAPI diff is non-breaking                                      |
| New dependency                     | Justify it in the PR: why not the stdlib, what is its maintenance status, what is its licence |
| Prompt changes                     | Attach golden-set regression results                                                          |
| New env var                        | Added to `.env.example`, [12](12-environment-variables.md), and every deployment environment  |

## 6. Issue conventions

Labels: `type:feat|bug|chore|docs|refactor` · `area:web|api|worker|ml|db|infra` ·
`priority:p0|p1|p2` · `size:s|m|l` · `blocked` · `good-first-task`

Bug reports state: what happened, what was expected, steps to reproduce, environment, and the
`requestId` from the error message — that last one turns a bug report into a log query.

## 7. Documentation

Update docs **in the same PR** as the change. Documentation that lags the code is worse than none,
because it is confidently wrong and someone will trust it.

- Behaviour change → the relevant `docs/` file
- Non-obvious decision → an [ADR](adr/README.md)
- New env var → `.env.example` + [12](12-environment-variables.md)
- New endpoint → OpenAPI annotations with an example
- Structural change → [10](10-folder-structure.md)

## 8. Working with the supervisor

- Tag the supervisor on PRs that change **architecture, scoring rules, or scope** — those are the
  decisions the FYP is graded on.
- Keep [01 §7 — Assumptions register](01-project-overview.md#7-assumptions-register) current. It is the
  fastest way for a supervisor to see what was inferred rather than specified, and to overrule any single
  inference cheaply.
- Record every accepted change of direction as an ADR, so the final report can trace _why_ the system
  looks the way it does — which is most of what a defence is about.

## 9. Definition of Ready (before starting an issue)

- [ ] Acceptance criteria are written and unambiguous
- [ ] The affected layers are identified
- [ ] Any API contract change is agreed with the other developer
- [ ] Any new assumption is recorded in [01 §7](01-project-overview.md#7-assumptions-register)
- [ ] It is small enough to finish in ≤ 3 days

## 10. Definition of Done

See [13 §9](13-coding-standards.md). In short: acceptance criteria met, tested, `make ci` green, types
strict, docs updated, migration reversible, no secrets or PII committed, peer-approved.
