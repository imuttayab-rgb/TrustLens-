# TrustLens local MinIO browser-upload hotfix

**Scope:** Narrow follow-up to the live face scan pilot. The browser could load `/face-scan/face_landmarker.task` (HTTP 200) and the worker loaded `FACE_MATCH_REAL_IN_DEMO=True`, but ID/selfie uploads would still fail: `STORAGE_ENDPOINT_URL=http://minio:9000` is only resolvable inside the Docker network.

## Change

- Keep `STORAGE_ENDPOINT_URL=http://minio:9000` for API and worker object operations.
- Add `STORAGE_PUBLIC_ENDPOINT_URL=http://localhost:9000` for **presigned browser POST uploads and GET downloads**. The API signs directly using the public hostname with the same S3 keys/region, rather than changing a signed URL's hostname (which would invalidate an AWS SigV4 GET signature).
- If the public endpoint is unset, the old single-endpoint behavior remains unchanged. No schema migration; no change to the admin/web/worker images.
- In Docker Compose, pass the public endpoint to the API through the existing shared backend environment map. The worker may receive the variable but does not need rebuilding to read existing objects at the original internal address.

**CORS already verified on the owner's laptop:** `OPTIONS` to `http://localhost:9000/trustlens-documents/test-only` with `Origin: http://localhost:3000` and `Access-Control-Request-Method: POST` returned `204 No Content`, `Access-Control-Allow-Methods: POST`, and `Access-Control-Allow-Origin: http://localhost:3000`. No MinIO CORS change is needed for this local web origin.

## Local activation after applying this patch

The owner's private `.env.production` backup already exists at `.git/trustlens-live-face-backups/20261001-091136/env-before-face`. Before editing further, take a second backup (local only; never share its contents). Append **exactly one** setting if not already present:

```dotenv
STORAGE_PUBLIC_ENDPOINT_URL=http://localhost:9000
```

Build **only** the API image while the old API remains running:

```bash
docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production build api
```

If successful, recreate **only** the API container:

```bash
docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production up -d --no-deps api
```

Verify `/health/ready` and `/health/worker`, then request an upload intent using a **synthetic authorized test seller and synthetic image only**; the returned URL must start with `http://localhost:9000/`. Check MinIO browser CORS preflight and the actual signed upload; do not use real CNICs or selfies in an unreviewed FYP setup.

**Rollback:** remove or comment only `STORAGE_PUBLIC_ENDPOINT_URL` and recreate the previous API image. This returns old browser upload URL behavior; no database, storage buckets or object contents are modified by the configuration itself. If CORS rules were changed separately, roll those back independently.

**Network boundaries:** `localhost` works only in a browser on the same laptop; a phone over LAN needs a phone-reachable URL and HTTPS for camera APIs. Production requires a browser-reachable HTTPS storage origin and a focused CORS allowlist; this localhost recipe is for the FYP laptop only. Never expose MinIO's admin console (`:9001`) as the presign origin.
