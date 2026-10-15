# TrustLens — hold physical ID beside face (opt-in FYP pilot)

**Status:** implemented in the reviewed source checkout, not automatically deployed to the owner's Windows Docker stack. This is NOT NADRA integration, certified liveness, document authenticity, or identity proofing certification.

## Four-step seller flow

1. Consent to biometric processing; camera is stopped immediately when consent is withdrawn.
2. Webcam-only separate CNIC front and back scan (clear card text and portrait).
3. Separate live face scan with look-up/down guidance.
4. Hold the **front** of the physical card beside the applicant's face in the same frame; keep both visible through guided head poses. A final unmirrored JPEG is privately uploaded. No gallery input is offered when this pilot is enabled.

The frontend can be bypassed by a modified client or virtual camera. The server therefore **requires** a fourth file with purpose `HOLD_ID`, validates ownership/purpose/non-reuse, stores it in the sensitive private-document bucket under the normal identity-media expiry, and binds its file ID to the exact verification attempt in existing JSONB metadata. An additive PostgreSQL enum migration adds `HOLD_ID` (no table or data reset).

The worker applies OpenCV ORB/homography matching between the separate front scan and the held-card frame and compares the holder's face with the separate selfie using the configured face engine; the front-card portrait is already compared with the selfie. ORB is not card authenticity; a high score from a fake face adapter is not treated as a real match. Every submitted hold-card case stays **PENDING for a human reviewer**, even if all automatic checks look good. Existing low-quality images are not automatically called fraud. Reviewers see all four private frames via short-lived signed URLs, the visual-check metrics and their usual audit/decision controls. While review is pending, the ID document and face signals remain unavailable, not verified. Approval/rejection now updates the underlying verification record **and** seller status in one audited transaction before recomputing the score. It is a manual verdict, not a NADRA verdict.

## Flags and rollout

- `NEXT_PUBLIC_HOLD_ID_SCAN=true`: compile-time seller web switch; implies the existing live-ID and live-face UI even if their separate flags are absent. A web **rebuild** is required. Disabled by default.
- `HOLD_ID_REQUIRED=true`: API refuses any identity submission without a fourth file. Keep this **off until all four new images** (API, worker, admin, web) are built and the additive migration succeeds.
- Existing three-file flows remain valid when the new flag is off. Disabling the backend requirement allows the legacy endpoint again. The PostgreSQL enum addition remains after rollback; old application images should not read new `HOLD_ID` rows without a compatibility assessment.
- Roll out with **new source/images → additive migration → API/worker/admin → web**; back up local env/image IDs first. Never rerun initial setup scripts, clear database volumes, or print secrets.

## Verification performed without real biometric data

- 53 Python cases in the combined focused worker/API/core run: synthetic card pattern matching and negatives; legacy/four-file Pydantic parsing; cross-user upload rejection; pending-score gate; reviewer approve/reject persistence and decision scenarios.
- 20 seller-web Vitest cases (pose/document challenges, marketplace regressions and a consent/no-gallery SSR UI test); web and admin type checks and targeted Python/TypeScript lint.
- Optimized web/admin builds compiled in isolated sandbox. No actual Windows webcam, real CNIC, full presigned upload to the owner's MinIO, staff reviewer login, or phone-camera performance has been verified. A live dry run must use synthetic TEST-ONLY card/images and an authorized staff demo account.

## Review checklist and limitations

The reviewer should compare front/back consistency, read the card portrait, inspect the face beside the card, compare that face to the separate selfie, check blur/glare and OCR provenance, then record a reasoned approval or rejection. Unreadable evidence merits a request to retry/manual clarification, not an automatic fraud label. Current admin review decisions offer approve/reject, not a dedicated rescan/request-more-info state. The fake OCR mode remains a **demo** and cannot authenticate a real CNIC. No server-verified video challenge or device-camera attestation is present. A still frame cannot rule out a printed face, replay, virtual camera, stolen card, or deepfake; phone cameras may improve focus but cannot be guaranteed to work perfectly. See NIST [remote identity-proofing guidance](https://pages.nist.gov/800-63-4/sp800-63a.html) for the distinction between capture, evidence validation and presentation-attack detection.

Before commercial deployment, check the license for the selected pretrained face-model weights (including InsightFace), adopt a legally permitted model/provider, complete privacy/legal review, and measure false accepts/rejects on a lawful, representative dataset. This academic pilot supplies no production accuracy or commercial-use certification.
