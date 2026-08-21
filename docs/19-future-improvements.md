# 19 — Future Improvements

The proposal lists the future scope explicitly:

> _"reverse-image stolen-photo detection, chat scam-detection, direct marketplace integrations,
> reputation history, and a mobile version."_

None of these is built. Each has a **seam** already in the architecture so that building it later is an
addition rather than a redesign. This document says exactly what the seam is and what remains to be done.

## 1. Reverse-image stolen-photo detection

**Seam already in place:** `listing_images.perceptual_hash` and `sha256` are computed at upload time and
indexed. This matters because hashes **cannot be backfilled** once images are purged under the retention
policy — computing them now costs nothing and preserves the option.

Remaining work:

1. Add a similarity search over pHashes (Hamming distance ≤ threshold) — `pg_bktree`, or a vector index
   on a CNN embedding.
2. Compare each new listing image against (a) other listings on TrustLens, and (b) an external
   reverse-image API for photos lifted from the web.
3. Add a signal `LISTING_IMAGES_ORIGINAL` (~8 points) with reason codes
   `IMAGE_REUSED_ACROSS_SELLERS` / `IMAGE_FOUND_ONLINE`.
4. Seed it into a new scoring model version, simulate, then activate.

Effort: medium. Highest fraud-detection value of the five items — stolen photos are named directly in the
problem statement, and image reuse across sellers is one of the strongest single fraud indicators.

## 2. Chat scam detection

**Seam:** the `LlmAnalyzer` port and the analysis-storage pattern generalise from listings to messages.

Remaining work:

1. New entities: `conversations`, `messages` (with strict retention and consent — message content is far
   more sensitive than listing text).
2. A `MessageAnalyzer` port and adapter reusing the LLM infrastructure; detect advance-fee patterns,
   off-platform payment pushes, urgency, and impersonation.
3. Signal `CHAT_BEHAVIOUR_SAFE` plus **real-time buyer warnings**, which is where the product value is —
   a warning during the conversation prevents the payment; a score change after it does not.
4. Privacy design: this is the most intrusive feature in the roadmap. It requires explicit opt-in,
   ephemeral analysis (analyse and discard, store only labels), and a clear notice to both parties.

Effort: large — mostly because the privacy and consent design is harder than the detection.

## 3. Direct marketplace integrations

**Seam:** `api_clients`, `api_keys`, `marketplaces`, `webhook_endpoints`, `webhook_deliveries`, and
`listings.source = API` all exist. The public API already supports partner-initiated seller creation (A3).

Remaining work:

1. A pull-based ingestion adapter per partner (their listing API → our `listings`).
2. An embeddable **trust badge** (iframe or script) that marketplaces render on a seller's page —
   probably the single highest-leverage distribution feature, since it puts the score where buyers
   actually are.
3. Partner sandbox environment with `tl_test_` keys and synthetic data.
4. Bulk endpoints and asynchronous batch scoring for large catalogues.
5. Self-serve partner portal for key management and usage.

Effort: medium. Highest commercial value.

## 4. Reputation history

**Seam:** `trust_scores` is already append-only with `computed_at`, and `GET /sellers/{id}/trust-score/history`
already exists. Most of this feature is a read model, not a schema change.

Remaining work:

1. Aggregate views: score trend, time-at-each-risk-level, verification milestones.
2. Buyer-facing signals derived from stability — _"verified for 8 months, score stable"_ is more
   persuasive than a single number, and much harder to fake than a fresh 100.
3. New signal `SCORE_STABILITY` rewarding a consistently good history.
4. Optional: buyer-submitted transaction outcomes (with heavy abuse protection — a review system is a
   new fraud surface, not just a new feature).

Effort: small-to-medium. Best value-per-hour of the five.

## 5. Mobile version

**Seam:** the API is already the only backend; the web app is a client of the same contract, and
`packages/api-client` is generated from OpenAPI.

Remaining work:

1. React Native (Expo) app in `apps/mobile`, reusing `packages/api-client`, `packages/validation`,
   `packages/constants`, and `packages/i18n`.
2. Native camera capture for CNIC and selfie — materially better OCR and face-match input quality than a
   browser file picker, which would likely raise verification success rates.
3. Push notifications for verification and appeal outcomes.
4. Device attestation (Play Integrity / App Attest) — a much stronger DEVICE signal than a browser
   fingerprint.
5. Extract shared UI primitives to a platform-agnostic package, or accept a separate mobile UI layer.

Effort: large. Note that items 2 and 4 would _improve the core product_, not just add a channel.

## 6. Additional improvements (beyond the proposal)

Not in the proposal's future scope; recorded here so they are considered deliberately rather than
drifted into.

| Improvement                                                                                     | Value                                                                       | Effort |
| ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ------ |
| **Fraud-ring / graph analysis** — cluster sellers by shared device, IP, CNIC, phone, image hash | Very high — catches organised fraud that per-seller scoring misses entirely | Large  |
| **Active-learning loop** — feed confirmed appeal outcomes back into classifier training         | High — the model improves from real labels instead of static ones           | Medium |
| **Score explanations in Urdu** — the i18n seam exists (A12)                                     | High for the target market                                                  | Small  |
| **Seller verification badge / shareable proof link**                                            | Medium — gives honest sellers a reason to participate                       | Small  |
| **Buyer scam reporting** with reviewer triage                                                   | High signal value; needs abuse protection                                   | Medium |
| **Liveness detection** (blink/pose challenge)                                                   | High — closes the printed-photo attack on face match                        | Medium |
| **Model card + fairness report** published per scoring model version                            | High for defensibility and for the FYP report                               | Small  |
| **Admin analytics dashboard** — fraud rates by marketplace, signal effectiveness                | Medium                                                                      | Medium |
| **A/B testing of scoring models** — shadow-score a fraction of sellers before activation        | Medium                                                                      | Medium |

## 7. Suggested sequence after the FYP

1. **Reputation history** — mostly a read model over data that already exists; fastest visible win.
2. **Reverse-image detection** — the hashes are already stored; directly attacks a named fraud pattern.
3. **Trust badge + partner sandbox** — turns the API from a demo into a distribution channel.
4. **Liveness detection** — closes the most obvious hole in the strongest signal.
5. **Fraud-ring graph analysis** — the largest step change in detection capability.
6. **Mobile app** — significant effort, but improves capture quality and device attestation.
7. **Chat scam detection** — highest privacy burden; do it last, and do it carefully.
