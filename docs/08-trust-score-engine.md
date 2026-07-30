# 08 — Trust Score Engine

The proposal's central requirement: *"combines all signals into a single Trust Score (0–100) with a clear
risk level and the reasons behind it"* and *"clearly showing why a seller is low, medium, or high risk."*

## 1. Design principle: deterministic rules, AI as evidence

```
   AI models produce EVIDENCE                Rules produce the SCORE
   ─────────────────────────                ────────────────────────
   EasyOCR  → text + confidence      ┐
   DeepFace → similarity + distance  ├──►  SignalCollector ──► ScoringPolicy(model_version)
   LLM      → labels + findings      │            │                      │
   Classifier → probability          ┘            │                      ▼
   IP intel → vpn/proxy/asn                       │            score, risk_level,
   DB facts → age, device links, OTP state ───────┘            per-signal breakdown
```

An LLM cannot be the arbiter of a score for three reasons that matter for this specific product:

1. **Appealability.** A seller who appeals is entitled to an explanation that does not change on re-ask.
2. **Reproducibility.** The same inputs must produce the same score, or the FYP evaluation is unrepeatable.
3. **Auditability.** "The model said so" is not a defensible basis for labelling a real person a fraud risk.

So AI outputs land in `listing_analyses`, `identity_verifications`, and `ip_addresses` as *evidence with
confidence values*, and a versioned weighted rule set converts evidence into points.

The LLM is still used for one thing in the scoring path: **rephrasing** a rule-derived reason code into a
friendly sentence for the buyer-facing summary. It is given the facts and the decision, and may only
reword them; if it is unavailable, the stored template text is shown instead.

## 2. Signals (v1 model — 100 points)

| Code | Category | Points | Evidence source | PASS condition |
|---|---|---:|---|---|
| `IDENTITY_DOCUMENT_VALID` | IDENTITY | 15 | `identity_documents` | CNIC OCR succeeded, fields parsed, not expired, quality ≥ threshold |
| `IDENTITY_FACE_MATCH` | IDENTITY | 15 | `identity_verifications` | DeepFace similarity ≥ threshold, liveness gate passed |
| `PHONE_VERIFIED` | PHONE | 10 | `phone_numbers.verified_at` | OTP completed |
| `PHONE_NOT_DISPOSABLE` | PHONE | 5 | `phone_numbers.line_type` | line type `MOBILE`, not flagged disposable |
| `EMAIL_VERIFIED` | EMAIL | 6 | `email_addresses.verified_at` | Verification link consumed |
| `EMAIL_NOT_DISPOSABLE` | EMAIL | 4 | `email_addresses` | Not a disposable domain, MX valid, domain age ≥ 180 d |
| `DEVICE_NOT_SHARED` | DEVICE | 6 | `user_devices` | ≤ 2 accounts share any of this seller's devices |
| `DEVICE_CONSISTENT` | DEVICE | 4 | `devices`, `access_events` | Not an emulator/bot; stable device history |
| `NETWORK_NOT_VPN` | NETWORK | 6 | `ip_addresses` | No VPN/proxy/Tor/datacenter IP in recent access events |
| `NETWORK_GEO_CONSISTENT` | NETWORK | 4 | `ip_addresses` vs `seller_profiles.country_code` | Country matches the declared country |
| `ACCOUNT_AGE` | BEHAVIOUR | 6 | `seller_profiles.account_opened_at` | Graded: ≥180 d full, 90–179 d 4, 30–89 d 2, <30 d 0 |
| `ACTIVITY_CONSISTENT` | BEHAVIOUR | 4 | `access_events` | Regular activity, no burst-then-vanish pattern |
| `LISTING_CONTENT_SAFE` | LISTING | 10 | `listing_analyses` (LLM + classifier) | Mean listing risk below threshold, no critical scam labels |
| `LISTING_PRICE_REALISTIC` | LISTING | 5 | `listing_analyses.price_deviation_pct` | Price within category norms |
| | **Total** | **100** | | |

The 30 points on IDENTITY reflect that the CNIC + face check is the hardest signal to forge and the one
the proposal foregrounds. PHONE + EMAIL together (25) cover the "throwaway contact" pattern.
DEVICE + NETWORK (20) cover "multiple accounts from one device". LISTING (15) covers
"too good to be true". BEHAVIOUR (10) covers account age. Every weight traces to a named fraud pattern.

Weights live in `scoring_weights` and are tunable by an admin; this table is the **seeded v1 default**.

## 3. Signal statuses

| Status | Meaning | Points |
|---|---|---|
| `PASS` | Check performed, passed | Full |
| `PARTIAL` | Passed with reservations (graded signals) | Fractional |
| `FAIL` | Check performed, failed | 0 |
| `UNAVAILABLE` | Could not be performed (provider outage, timeout) | Excluded from the denominator |
| `NOT_APPLICABLE` | Doesn't apply (e.g. no listings yet → `LISTING_*`) | Excluded from the denominator |

## 4. Scoring algorithm

```
1. Collect signal evaluations for the seller.
2. available_weight = Σ points_possible where status ∉ {UNAVAILABLE, NOT_APPLICABLE}
3. earned         = Σ points_awarded
4. If available_weight < MIN_EVIDENCE_WEIGHT (default 40):
        → score = 0, risk_level = UNKNOWN, reason = INSUFFICIENT_EVIDENCE
        → STOP.  (An unverified new seller is "unknown", not "high risk".)
5. raw_score = (earned / available_weight) × 100
6. Apply hard caps: for each critical signal with status = FAIL,
        score = min(score, cap_for_that_signal)
7. score      = round(clamp(raw_score, 0, 100))
8. risk_level = band(score)
9. confidence = weighted mean of per-signal confidences, scaled by evidence coverage
10. Persist trust_scores + one trust_score_signals row per evaluated signal.
```

### Normalisation (step 5) — why

If the LLM provider is down, `LISTING_CONTENT_SAFE` is `UNAVAILABLE`. Scoring it as 0 would drop a fully
verified seller from 100 to 90 because of *our* outage. Normalising over the weight actually evaluated
keeps the score fair, and the response lists `unavailableSignals` so the consumer knows the evidence base
was narrower than usual. `confidence` drops accordingly, which is the honest way to express "this score is
based on less information".

### Hard caps (step 6) — why

A weighted sum alone can be gamed. A seller who fails face match but passes everything else would score
~85 — "low risk" — which is exactly wrong. Caps encode non-negotiables:

| Failed critical signal | Score capped at | Rationale |
|---|---|---|
| `IDENTITY_FACE_MATCH` = FAIL | 25 | The selfie doesn't match the ID; identity is unproven |
| `IDENTITY_DOCUMENT_VALID` = FAIL (forged/expired) | 20 | Document itself is not trustworthy |
| Duplicate CNIC across ≥3 accounts | 15 | Classic multi-account fraud |
| Device shared with a banned account | 10 | Ban evasion |
| Admin manual flag | 20 | Human judgement overrides arithmetic |

Caps are `hard_cap_on_fail` values on `scoring_weights`, so they are versioned and tunable like weights.
`cap_applied` is stored on `trust_scores` so an appeal review can see instantly that the score was clamped
rather than computed.

### Risk bands (ASSUMPTION A1)

| Band | Range | Buyer-facing meaning |
|---|---|---|
| **LOW** | 70–100 | Multiple independent checks passed; proceed with normal caution |
| **MEDIUM** | 40–69 | Partly verified; ask for more proof before paying |
| **HIGH** | 0–39 | Weak or contradicted verification; high scam risk |
| **UNKNOWN** | insufficient evidence | Not enough checks completed to judge |

`UNKNOWN` is a deliberate fourth state that the proposal does not name but the product needs: a
brand-new honest seller and a proven scammer must not be shown identically. The UI renders `UNKNOWN` in
neutral slate, never in red or green.

## 5. Explainability

Three levels, each generated from `trust_score_signals` — no recomputation, no LLM dependency:

1. **Score + band** — `74 / LOW`
2. **Category rollup** — Identity 30/30 · Phone 10/15 · Email 10/10 · Device 10/10 · Network 6/10 …
3. **Reasons** — every signal's `reason_code` + `reason_text`, ordered by absolute point impact
   (largest losses first, because "why am I not higher" is the question sellers actually ask).

Reason codes are stable strings so the frontend can localise them and partners can switch on them:

| Reason code | Text |
|---|---|
| `IDENTITY_VERIFIED` | Government ID verified with a matching selfie. |
| `FACE_MATCH_LOW` | The selfie does not clearly match the photo on the submitted ID. |
| `CNIC_EXPIRED` | The submitted ID has expired. |
| `PHONE_LINE_TYPE_VOIP` | The phone number is an internet number rather than a mobile SIM. |
| `EMAIL_DOMAIN_DISPOSABLE` | The email address uses a temporary email service. |
| `DEVICE_SHARED_MANY_ACCOUNTS` | This device is linked to several other seller accounts. |
| `NETWORK_VPN_DETECTED` | The seller connects through a VPN or proxy, hiding their location. |
| `GEO_MISMATCH` | The seller's connection location doesn't match their stated location. |
| `ACCOUNT_TOO_NEW` | The account was created very recently. |
| `LISTING_URGENCY_PRESSURE` | Listings use pressure tactics such as "pay now, others are waiting". |
| `LISTING_OFF_PLATFORM_CONTACT` | Listings push buyers to move the conversation off-platform. |
| `PRICE_TOO_GOOD_TO_BE_TRUE` | Prices are far below the normal range for similar items. |
| `INSUFFICIENT_EVIDENCE` | Not enough checks have been completed to judge this seller. |

Sellers additionally get `GET /sellers/{id}/trust-score/improvements`: the unearned points, ranked by
value, each with the action that would earn them ("Verify your phone with a mobile SIM: +15 points").
This turns the score from a verdict into a path — the difference between a system sellers resent and one
they cooperate with.

## 6. Recomputation triggers

`ComputeTrustScore` is invoked by a domain event, never inline in a request handler:

| Trigger | Event | Enum |
|---|---|---|
| Identity approved/rejected | `IdentityVerified` / `IdentityRejected` | `SIGNAL_CHANGE` |
| Phone/email verified or changed | `PhoneVerified` / `EmailVerified` | `SIGNAL_CHANGE` |
| New device or IP observed | `DeviceLinked` / `SuspiciousNetworkDetected` | `SIGNAL_CHANGE` |
| Listing analysed | `ListingAnalysed` | `SIGNAL_CHANGE` |
| Admin override | `TrustScoreOverridden` | `MANUAL` |
| Appeal resolved | `AppealResolved` | `APPEAL_RESOLUTION` |
| Scoring model activated | `ScoringModelActivated` → bulk backfill job | `MODEL_CHANGE` |
| Nightly staleness sweep | cron over `valid_until < now()` | `SCHEDULED` |
| Public API miss on an expired score | on-demand | `API_REQUEST` |

**Debouncing.** A verification burst (identity + phone + email within seconds) would trigger three
recomputations. A per-seller Redis dedup key with a 10-second window collapses them into one, and the
scoring job takes a per-seller lock so two computations can never race to set `is_current`.

## 7. Model versioning

Each `trust_scores` row references the `scoring_models` row that produced it. Consequences:

- A score computed in March under v1.0 stays explainable after v1.1 activates in June.
- Activating a new model does **not** rewrite history; it enqueues `bulk_recompute_for_model`, which
  writes new score rows and leaves the old ones as history.
- `POST /admin/scoring-models/{id}/simulate` runs a **draft** model over a sample and returns the
  distribution shift (how many sellers move band, mean delta, biggest movers) before activation.
- Only one model may be active — enforced by a partial unique index, not by convention.

## 8. Manual override & appeals

An admin may override a score, but the design makes overriding expensive on purpose:

- `override_reason` is **required** (DB check constraint).
- The override writes a new `trust_scores` row with `is_manual_override = true` and `trigger = MANUAL` —
  the computed score it replaced remains in history.
- An `audit_logs` entry records actor, before, after, and reason.
- Overridden scores expire after 90 days and revert to computed scores unless renewed, so a one-off
  human decision cannot silently become permanent.

Appeal flow: seller submits an appeal against a specific `trust_score_id` → a `review_case` is created →
a reviewer sees the full signal breakdown plus the underlying evidence (OCR output, face similarity,
device cluster) → decision is either *recompute* (evidence corrected), *override* (with reason), or
*reject* (with explanation). Every outcome notifies the seller and is audit-logged.

## 9. Fairness and error-cost considerations

The system labels real people as fraud risks. Two guardrails follow from that:

- **False positives are more harmful than false negatives here.** Wrongly marking an honest seller HIGH
  risk costs them their livelihood; wrongly marking a scammer MEDIUM costs a buyer one extra check. So
  automatic *demotion* thresholds are conservative, and every high-risk automatic outcome that a seller
  appeals goes to a human, not to an automated re-check.
- **Face matching has known demographic error-rate disparities.** The threshold is therefore set with a
  deliberate margin, a borderline band (`0.55–0.70` similarity) routes to **manual review** instead of an
  automatic FAIL, and `IDENTITY_FACE_MATCH` never triggers a hard cap on the borderline band alone.

`apps/ml` tracks per-signal false-positive/false-negative rates against the labelled evaluation set so
threshold changes can be argued with numbers rather than intuition.
