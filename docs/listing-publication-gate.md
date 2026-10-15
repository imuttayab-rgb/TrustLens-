# TrustLens — verify seller before listing goes live

**Scope:** incremental FYP security change on top of the hold-ID beside-face pilot and marketplace category fix. No database migration, external service, real ID fixture, or GitHub push is required. Application source and targeted API/worker/web images change; PostgreSQL, Redis, MinIO and existing user content are retained.

## Rule

A seller may register, save/edit a listing and run its scam-risk analysis. The listing is **not buyer-visible** until all of the following are true:

1. The seller's identity status is `VERIFIED` (in the current hold-ID pilot, a human reviewer must decide). `PENDING`/`REJECTED`/`FAILED` do not count.
2. Phone **and** email statuses are `VERIFIED`, the seller is not flagged or deleted.
3. That listing has completed analysis with a risk score **below 60**, is not removed/expired/sold/flagged, and is in the public `ACTIVE` state.

No 100/100 Trust Score requirement: risk scoring and account verification are not the same thing. A private `DRAFT` is owner-readable but absent from marketplace searches, direct public listing URLs and buyer favorites/counts. Direct message creation, new offers, and auctions/bids check seller eligibility again on the server. Pre-existing conversations can remain accessible to their participants; seller revocation should not erase transaction records.

When the final seller verification arrives, qualifying analysed private drafts are released automatically. Revocation/rejection hides active listings; a guarded status-only SQL update preserves each item's latest analysis and avoids overwriting seller edits. A concurrently changed listing analysis is rolled back instead of published. Unsafe, unanalyzed, removed or previously flagged listings do **not** auto-release.

## Honest identity-evidence boundary

The local FYP stack may use `USE_FAKE_AI=true`: **fake OCR fabricates a card number and expiry based on image bytes**. This patch stops a fake OCR result from supplying a duplicate-ID hash, from causing an automatic expired-ID refusal, or from being treated as a conclusive machine identity decision. It explicitly sends the application for human review and labels the OCR provenance `fake`. Do not claim a real CNIC expiry was read or a NADRA match was performed. The opt-in real face matcher compares images; camera movement is **not certified presentation-attack detection**. Real document OCR, auditable reviewer operations, actual email/SMS delivery and permissioned identity datasets remain separate production work.

## Existing-demo impact

The sample data includes low/medium/high-risk sellers. The medium/high seeded seller identities may be `REJECTED`, so **their existing sample listings will disappear from buyer search** under the correct new policy; the records are not deleted and stay available to the owner/staff. Do not bypass verification just to restore illustrative ads; use a clearly labeled demonstration mode or verified synthetic fixtures for a fuller viva marketplace.

## Laptop rollout

From the *existing* TrustLens repository on commit `3fb1136` with the previously delivered patches already applied, extract the companion ZIP and run `bash "$HOME/Downloads/TrustLens_Publication_Gate/TrustLens_Publication_Gate/install-publication-gate.sh"` from Git Bash. Its source patch is incremental. It keeps your local Docker build fixes, `.env.production`, secrets, existing volumes and unmodified service images. It backs up the local source patch and old image tags, builds API, worker and seller web before targeted service recreation, then checks `/health/ready`, `/health/worker` and `/browse`. There is **no migration or seed command**. It refuses unexpected source/commit changes; do not reset/force it through a developer update.

If a build or health check fails, the installer restores old image tags and recreates the prior running app containers as needed. It leaves the new source in the Git working tree to diagnose/retry, and never discards existing edits. It does not push to GitHub. The backup directory and old image tags are printed. Do not claim rollout is complete until laptop health and a real synthetic-account user journey pass.

## Acceptance test (synthetic data only)

- Unverified seller saves an ad; owner sees `PRIVATE DRAFT` or verification notice, buyer search/direct URL/favorites do not see it, and an offer or new conversation cannot be created from the ID.
- Identity pending while phone/email are verified: private. Phone/email pending while identity is approved: private.
- Reviewer approves identity; phone/email are verified; item analysis score <60: draft becomes `ACTIVE` and buyer can open it. Reviewer rejects/revokes: the item immediately becomes hidden; no stored listing or analysis is erased.
- High-risk (>=60), no analysis, flagged/removed/expired/sold items remain blocked despite seller approval.
- Account Trust Score 20/100 or another non-perfect value does **not** itself stop a verified seller from publishing a safe item.
- Fake OCR cannot silently mint a verified identity or reject on its synthetic CNIC/expiry; staff see real evidence and the simulated-provenance warning.
- Confirm Postgres/Redis/worker and existing seller dashboard still respond; do not use a real CNIC or personal biometric in testing.

**Test evidence (isolated sandbox):** seller web typecheck, focused ESLint and 20 Vitest checks; core/worker/AI pytest regressions including new buyer query, concurrency and reviewer release checks; four focused API storage/identity-schema checks; Ruff, Python bytecode checks; seller web production build using the laptop's known temporary lint/type bypass. A laptop-side end-to-end buyer/verification path remains to be verified after installation.
