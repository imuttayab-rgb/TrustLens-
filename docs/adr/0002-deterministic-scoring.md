# ADR-0002: A deterministic rule engine computes the Trust Score; AI provides evidence

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Haseeb Ur Rehman, Muhammad Muttayab

## Context

The proposal requires *"an explainable Trust Score engine with risk levels"* that *"clearly shows why a
seller is low, medium, or high risk"*, and lists OpenAI/Claude, OpenCV, EasyOCR, DeepFace, and a
custom-trained classifier as the AI engine.

The obvious-looking design is to hand all evidence to an LLM and ask it for a score and an explanation.
That design fails three requirements this system actually has: appeals, reproducibility, and audit.

## Decision

AI components produce **evidence with confidence values**. A versioned, deterministic weighted rule set
converts evidence into points, a score, and a risk band. Every computation persists a full per-signal
breakdown (`trust_score_signals`).

An LLM may **rephrase** a rule-derived reason code into friendly prose for the buyer-facing summary. It
is given the facts and the decision and may only reword them; if it is unavailable, stored template text
is used.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **LLM computes the score** | Non-reproducible (same input, different output), unappealable ("the model said so" is not a defence when labelling a real person a fraud risk), unauditable, and directly vulnerable to prompt injection via seller-controlled listing text — the LLM's input is written by the person being scored |
| **Trained end-to-end ML model produces the score** | Needs labelled fraud outcomes we do not have; a black-box score cannot satisfy the explainability requirement; a per-feature attribution method would be an approximation of an explanation rather than the actual reason |
| **Hardcoded weights in Python** | Simple, but every tuning change becomes a redeploy, and historical scores silently become inexplicable once the constants change |
| **Hybrid: rules with an LLM override** | Reintroduces every problem above at the exact moment it matters most (the borderline cases) |

## Consequences

**Positive**
- Same inputs + same model version ⇒ same score, always.
- Explainability is structural: the breakdown *is* the explanation, produced without an LLM call.
- Prompt injection is contained — the worst case is one wrong label on a signal worth ≤10 points, visible
  in the breakdown and appealable.
- Weights are tunable through the admin UI without a redeploy ([ADR-0007](0007-versioned-scoring-models.md)).
- The scoring policy is pure and fast, so it can be tested exhaustively (95% coverage gate).

**Negative / accepted costs**
- Weights are chosen by judgement rather than learned from data. Mitigated by the simulate-before-activate
  workflow and by the evaluation set in `apps/ml`.
- A rule engine cannot discover novel fraud patterns the way a learned model might. Mitigated by feeding
  the learned classifier's output in as one signal, where it contributes without controlling the outcome.

**Revisit if:** a large corpus of confirmed fraud outcomes accumulates and a learned model can be shown to
outperform the rules *while* producing per-signal attributions strong enough to satisfy an appeal.
