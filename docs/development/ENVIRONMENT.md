# Environment and secrets

| Location | Role |
| --- | --- |
| `.env.example` | Host-based developer template |
| `.env.production.example` | Docker localhost/public-deployment template; placeholder secrets only |
| `.env.hosted.example` | Optional hosted-service template |
| `.env.production` | Private, generated per installation; never included in this ZIP |
| `.trustlens-calls/livekit.yaml` | Private generated LiveKit key/configuration; never included |
| `trustlens/shared/config/settings.py` | Typed backend validation and production checks |
| `apps/web/src/config/environment.ts`, admin equivalent | Central public browser API origin |
| `features/verification/live-scan-flags.ts` and related flag modules | Existing browser build-time feature switches |
| `docker/compose/docker-compose.prod.yml` | Injects backend secrets/runtime values and browser build arguments |

Never put a secret in `NEXT_PUBLIC_*`: those values are compiled into downloadable browser JavaScript. Changing public URLs/flags needs rebuilding web/admin. Backend connection changes normally require recreation/restart. JWT/encryption key changes require a planned key/data migration, not a routine configuration refresh.

`init-env.sh` creates fresh random database/storage credentials and Ed25519/token/encryption secrets once; reruns preserve the existing file. `configure_calls.py` preserves existing media/VAPID keys and refuses non-local calling configurations. The launcher uses an isolated Compose project/image prefix. `LOCAL_BIND_ADDRESS` defaults to loopback; exposing a public server requires a deliberate proxy/TLS/network configuration.

Required local services are PostgreSQL, Redis, MinIO/S3, Mailpit/SMTP and LiveKit for calling. No paid calling key is required for self-hosted LiveKit; hardware/server/bandwidth still have resource costs. Google sign-in, real email/SMS, external AI and search providers are optional and require their own explicit configuration. Their keys are not included in this package. `USE_FAKE_AI=true` is a deterministic demonstration mode, not real identity validation.

Keep a secure copy of the original encryption keys with your recovery plan. Database and object backups cannot decrypt themselves after these keys are lost. Never send a live `.env` with the ordinary source ZIP.

## Security release settings

- Local `EMAIL_PROVIDER=smtp`, `SMS_PROVIDER=mailpit`: email links and SMS previews arrive at http://localhost:8025. This is a local demonstration, not real SMS delivery or proof of phone ownership. Old local `console` settings map to the same SMTP sink.
- Production refuses console/Mailpit SMS, unconfigured providers, insecure SMTP and disabled rate limiting. Set `SMS_PROVIDER=disabled` if real SMS is not configured; phone verification then cannot complete. There is no paid API requirement for local chat/calling.
- `RATE_LIMIT_LOGIN_IP_PER_MINUTE=5`, `RATE_LIMIT_EMAIL_SEND_PER_HOUR=3`, `RATE_LIMIT_SIGNUP_PER_HOUR=10`, `RATE_LIMIT_UPLOAD_PER_MINUTE=20`; quota defaults are 1 GiB / 1,000 reserved upload intents per account. Existing retained records are never purged to satisfy quota. Raise a quota only after reviewing capacity/abuse.
- Compose derives document CSP settings from `WEB_BASE_URL`, `ADMIN_BASE_URL`, `NEXT_PUBLIC_API_BASE_URL` and `CALLS_LIVEKIT_URL`. Add the browser-visible object-storage origin and any other required public origins to `CSP_CONNECT_ORIGINS` (space or comma separated). Plain Next hosting also accepts `CSP_APP_ORIGIN`, `CSP_API_ORIGIN`, `CSP_MEDIA_ORIGIN`. These runtime values are public origins, never secrets.
- API request/OTP/message limiters fail closed during Redis outages with a retryable error. Queue connectivity is required at startup; a failed enqueue never claims completion.
- Sentry exports sanitized error metadata only; request traces are disabled. `SENTRY_TRACES_SAMPLE_RATE` is retained for configuration compatibility but does not enable request tracing in this edition.
