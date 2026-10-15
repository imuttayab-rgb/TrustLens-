# TrustLens live face scan — opt-in FYP pilot

**Based on GitHub main commit:** `3fb1136` (1 October 2026). This change is isolated from the owner's live Windows Docker checkout. The repository's old identity flow remains the default unless the two explicit switches below are enabled.

## What the implementation actually does

- `LiveFaceScan.tsx` loads the pinned MediaPipe Face Landmarker and WASM **from TrustLens's own `/face-scan/` assets** when a consenting seller starts a scan; no images go to Google's servers.
- Browser camera tracks **exactly one face**, calibrates the initial pose, prompts two different held head movements (up/down in random order), then requires a neutral return. It captures one JPEG **without a printed ID held beside the face** so the worker recognizes the live face rather than accidentally selecting a portrait on the card.
- Existing `/verification/identity` upload/ownership/consent endpoint and asynchronous worker remain unchanged. The worker runs **1:1 comparison of the ID front's portrait to the captured face** with InsightFace when configured for real matching; this is not a NADRA lookup.
- With `USE_FAKE_AI=true`, the existing fake face matcher remains the default. `FACE_MATCH_REAL_IN_DEMO=true` opts into **real local InsightFace face matching only**, without requiring real OCR/LLM keys. OCR and other AI signals remain fake and must be identified as such in the FYP demonstration.
- Missing detectable faces in the opt-in real-face pilot are routed to manual review instead of an automatic fraud rejection. The original behavior is preserved when the pilot flag is off.

## Enable safely on a Windows laptop

1. Take a source backup, preserve the existing private `.env.production` **outside any shared archive**, and apply only this reviewed change to a checkout at commit `3fb1136`. Do not reset the database or discard the owner's three local build fixes (`apps/web/next.config.ts`, `docker/api.Dockerfile`, `docker/worker.Dockerfile`).
2. Set the following in the local `.env.production` **only after the new code is present**:

   ```dotenv
   NEXT_PUBLIC_LIVE_FACE_SCAN=true
   FACE_MATCH_REAL_IN_DEMO=true
   USE_FAKE_AI=true
   FACE_ENGINE=insightface
   ```

3. Rebuild and restart **only** `web` and `worker` with the existing Compose file and environment file. `NEXT_PUBLIC_LIVE_FACE_SCAN` is compiled into the web bundle, so a mere restart does not enable the UI:

   ```bash
   docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production build web worker
   docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production up -d --no-deps web worker
   ```

4. Check `http://localhost:3000/dashboard/verification/identity` while signed in as a test seller. Camera access works on `localhost` and HTTPS; **a plain LAN-IP `http://192.168...` address will generally not get browser camera access**. Keep a test account and use synthetic or authorized consented data only.
5. Check `http://localhost:8000/health/ready` and worker heartbeat; test face match against a consenting/test fixture, mismatch, no face, camera denial, phone, login and listings. No real biometric accuracy or anti-spoof acceptance rate has been established by this code review alone.

**Quick UI rollback:** Set `NEXT_PUBLIC_LIVE_FACE_SCAN=false`, rebuild/restart `web`. **Real matcher rollback:** Set `FACE_MATCH_REAL_IN_DEMO=false`, recreate `worker`. No database migration and no new face-template table are involved. Existing accounts, seller scores and the usual selfie capture remain in place.

## Tests executed in the isolated sandbox

- Web TypeScript `typecheck` and targeted ESLint passed; five deterministic challenge tests passed.
- AI adapter suite (70 tests) and worker suite (23 tests) passed; targeted Python Ruff passed.
- Next production build with the feature enabled **compiled and completed using the same temporary lint/type bypass that the owner's current local checkout already uses**. The unmodified upstream production build fails on pre-existing `dashboard/settings/page.tsx` ESLint errors unrelated to this feature. The temporary bypass was restored before the patch was exported.
- Local web server returned HTTP 200 for the homepage, model `.task` and both SIMD/non-SIMD WASM assets.
- Real InsightFace `buffalo_s` smoke test using the public NASA astronaut fixture returned similarity 1.0 for the same image and no face detected for a blank JPEG. **This is not a real CNIC accuracy benchmark.**
- **Not yet validated:** a genuine live camera scan on the owner's laptop; a full signed-in identity submission using a real ID; mobile performance, replay/virtual-camera resistance, and calibrated false-accept/reject rates.

## Security and FYP limitations

- The motion challenge is **client-side guidance**, not server-verified proof of physical presence. The backend gets a final still image only; a replay, virtual camera or tampered browser may bypass it. `liveness_passed` intentionally stays unknown (`None`), and no certified PAD/deepfake-resistance claim should be made.
- The 1:1 matcher compares a face against **the portrait on a user-submitted card**. Neither OCR nor visual similarity establishes that the card was issued by NADRA or that its text is authentic. With fake OCR enabled, do not call the document genuine.
- The pilot deliberately does **not** store searchable cross-account biometric embeddings, prevent repeat accounts, auto-ban faces, or change SMS/Gmail delivery. These remain separate future-work items.
- Review consent wording, encrypted storage and image retention before live use. For a real deployment, independently assess model licensing, accessibility, calibration and legal/privacy requirements.

**Source/model:** [Google MediaPipe Face Landmarker web docs](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js); model artifact is the published `float16/1/face_landmarker.task` with SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`. The npm package `@mediapipe/tasks-vision` is pinned to `0.10.32`. Real face weights are managed by the existing worker image and carry separate noncommercial/research licensing considerations.
