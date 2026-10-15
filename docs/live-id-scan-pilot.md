# TrustLens — webcam-only ID capture (FYP pilot)

**Goal:** Replace the seller's optional CNIC file pickers with live webcam capture for both sides while leaving the existing backend upload, OCR, 1:1 card-portrait/face comparison, worker, database, and marketplace routes intact.

## How it works

1. A distinct, default-off `NEXT_PUBLIC_LIVE_ID_SCAN` flag controls the seller verification UI. Without the flag the old `ImageCapture` file picker remains exactly as before. The owner can opt in after an isolated build/test; a Next.js rebuild is necessary.
2. The seller gives **informed consent before camera access**. Two `LiveIdScan` instances guide the front and then back through a rear-camera preference, falling back to a laptop/USB webcam. The browser's `getUserMedia` stream supplies frames directly; no HTML file input or gallery chooser is rendered for CNIC in this mode.
3. A central guide rectangle, brightness/glare checks and a coarse focus heuristic encourage readable frames. A randomized **left/right card movement** followed by returning to center requires short holds; the browser then automatically captures an unmirrored JPEG at the webcam's available resolution (capped at 1600 px width). The movement detector estimates horizontal texture translation and is only a presentation challenge. It does **not** verify actual card tilt, document authenticity, or PAD. No motion video or landmarks are uploaded.
4. Front, back, and the existing live face still use the existing private signed POST and identity submission endpoint. There is no database migration and no change to Trust Score rules. The worker's real face matcher must remain independently opted in (`FACE_MATCH_REAL_IN_DEMO=true`) for a real card-portrait-to-face comparison; `USE_FAKE_AI=true` leaves other demo AI behavior fake.
5. Both streams are stopped after capture/cancel, when consent is withdrawn, or when the component unmounts. Preview object URLs are revoked. A retake clears its previous frame. A 45-second timeout and precise camera-permission/quality errors avoid an endless spinner.

## FYP boundaries and limitations

- `getUserMedia` accepts **hardware and virtual camera sources**. A modified client, recorded video, screen showing a photo/card, fabricated physical card, or stolen real card may pass. The backend receives still images, not a signed sensor attestation or server-verified movement proof. No claim of NADRA, certified liveness, guaranteed genuine CNIC, or 100% scam prevention is warranted. See [NIST SP 800-63A](https://pages.nist.gov/800-63-4/sp800-63a.html).
- Browser motion, light and focus heuristics can reject a genuine user with an old blurry laptop webcam; a sharp fabricated card can also pass. Front-versus-back label is selected by the seller; actual content/field consistency still depends on OCR and manual review. Do **not** automatically label unclear cases fraudulent.
- `localhost` permits camera access on the same laptop; on a phone or another computer use HTTPS and a device-reachable API/storage origin. The existing IPv4-only local Docker host bindings are intentional for the owner’s Windows localhost issue and are not a phone handoff implementation. See [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).
- No real CNIC/selfie should be used for automated tests. Production use requires a legal/privacy review, explicit retention policy, an accessible camera-unavailable/manual-review path, robust anti-injection/PAD evaluation, and performance measurements across devices/lighting.

## Developer checks

```bash
pnpm --filter @trustlens/web typecheck
pnpm --filter @trustlens/web exec vitest run src/features/verification/components/id-scan-challenge.test.ts
pnpm --filter @trustlens/web exec eslint src/features/verification/components/LiveIdScan.tsx src/features/verification/components/id-scan-challenge.ts src/features/verification/components/IdentityVerification.tsx
```

To enable on the **owner's laptop only**, back up `.env.production` locally, append `NEXT_PUBLIC_LIVE_ID_SCAN=true` once, build **only** `web`, and after a successful build recreate **only** `web` with `--no-deps --no-build`. Keep the existing `NEXT_PUBLIC_LIVE_FACE_SCAN=true`, `FACE_MATCH_REAL_IN_DEMO=true`, `STORAGE_ENDPOINT_URL=http://minio:9000`, and `STORAGE_PUBLIC_ENDPOINT_URL=http://127.0.0.1:9000` unchanged. Never send the private env or real ID to collaborators.

**Rollback:** set `NEXT_PUBLIC_LIVE_ID_SCAN=false`, rebuild/recreate only `web`; the original file-picker UI returns. No API, worker, database, or storage data changes are required for this feature.

**Unverified until physical testing:** unit tests and a production build do not prove webcam autofocus quality, permission behavior, signed upload success, or ID-to-face accuracy on a real device. Test with synthetic/consented fixtures and document limitations before a viva demonstration.
