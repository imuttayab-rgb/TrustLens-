# ADR-0007: Scoring weights live in the database and are versioned

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Haseeb Ur Rehman, Muhammad Muttayab

## Context

[ADR-0002](0002-deterministic-scoring.md) established that a weighted rule set computes the score. Where
those weights live determines whether tuning is a deploy, whether historical scores stay explainable, and
whether a supervisor's "why is identity worth 30 points?" has a demonstrable answer.

Weights *will* change: during development, during evaluation, and in response to observed fraud patterns.

## Decision

Weights and thresholds live in `scoring_models` + `scoring_weights`. Every `trust_scores` row references
the model version that produced it. At most one model is active, enforced by a partial unique index.

Workflow: an admin edits a **draft** model → `POST /admin/scoring-models/{id}/simulate` recomputes a
sample and returns the distribution delta (how many sellers change band, mean delta, biggest movers) →
activation writes an audit log entry and enqueues a bulk recomputation that **appends** new score rows.
Old scores are never rewritten.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **Constants in Python** | Every tuning change is a redeploy; historical scores become inexplicable the moment the constants change; a supervisor cannot experiment during a demo |
| **A YAML/JSON config file in the repo** | Better history than constants, but still requires a deploy, and there is no clean way to point an old score at the config that produced it |
| **Environment variables** | Unmanageable for ~14 weights plus thresholds and caps; no versioning, no audit trail, no simulation |
| **Mutating weights in place with no versioning** | Silently invalidates every historical score and destroys the ability to defend a past decision in an appeal — the exact failure this system cannot afford |

## Consequences

**Positive**
- Tuning without a deploy; a supervisor can watch the effect of a weight change live.
- Historical scores remain explainable forever, because each cites its own model version.
- Simulation before activation makes weight changes an evidence-based decision instead of a guess with a
  global blast radius.
- Every activation is attributable in `audit_logs`.

**Negative / accepted costs**
- Weights become runtime data, so an invalid configuration is possible. Mitigated by an application
  invariant plus a DB check that enabled weights sum to 100, and by validating the model before activation.
- One extra query per scoring run to load the active model (cached in Redis, negligible).
- A bulk recompute after activation is a large background job; it must be rate-limited so it doesn't
  starve interactive verification jobs.

**Revisit if:** weights ever become learned rather than hand-tuned — the table would then store the
learned parameters, and the versioning and simulation machinery would still apply.
