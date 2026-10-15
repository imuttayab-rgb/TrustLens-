> Complete organized edition: use `START_HERE.md` / `scripts/local/start.sh` for a fresh laptop. Patch-installer commands below describe earlier incremental releases. The complete package already contains chat, recorded voice, calls and call controls.

# TrustLens browser voice calls

Implemented with LiveKit Server v1.13.9 (self-hosted, Apache-2.0), livekit-client 2.22.4, WebRTC/Opus and optional standard Web Push (pywebpush 2.5.0). No paid API, provider account, SIP service or phone number is required. Software has no per-minute fee. Your computer must run the local media server. Public hosting, domain and bandwidth may cost money; this implementation cannot make infrastructure free.

## What users get

- Private one-to-one calls from an eligible product conversation. Microphone access is requested only after the user starts or accepts a call.
- Calling, receiver-acknowledged Ringing, Connecting and Connected states; accept, decline, cancel, end, mute, input selection and output selection where supported.
- Speech audio with browser echo cancellation, noise suppression and automatic gain control; connection-quality and missing incoming-packet warnings. These are browser capabilities, not paid AI noise removal.
- Global call panel survives navigation inside the site. Reloading/closing the page ends its media session; opening another tab cannot take over an accepted call.
- One call per user, 45-second unanswered deadline, bounded reconnect attempts, 45-second server liveness lease, two-hour maximum call length, and five outgoing invitations per minute.
- Recent 30 calls per conversation, with outcome/duration. Clear My Chat also hides older calls for that user; backend metadata stays retained. No live call recording is made. Voice-message recordings are a separate feature.
- Product sold/inactive: existing 72-hour grace applies, then new and ongoing calls are disabled. Blocks and account restrictions are enforced on the server.
- Optional incoming/missed-call notifications. An invitation notification opens the chat; it does not answer automatically or guarantee native phone ringing.

## Localhost installer

Start the existing TrustLens Docker stack. Save `TrustLens_Voice_Calls_Install.sh`, then from Git Bash:

```bash
bash /path/to/TrustLens_Voice_Calls_Install.sh "$HOME/Documents/TrustLens"
```

Use your actual checkout path. The installer supports the recovered original checkout and the previously supplied chat/voice patch. It refuses conflicting source/runtime changes, snapshots source and generated configuration, preserves running image references, builds replacement images, encrypts a database backup and applies additive migrations. It does not downgrade or erase database records. Logs/recovery script stay under `.git/trustlens-voice-calls-backups/` on your machine.

Generated keys stay in `.env.production` and `.trustlens-calls/livekit.yaml` (excluded from Git and image build context). No keys are shipped in the package. Re-running the configuration helper preserves existing keys.

The local LiveKit Compose profile publishes 7880/TCP, 7881/TCP and 7882/UDP on loopback only. Open `http://localhost:3000` in two separate browsers or normal/incognito windows and log in to two different accounts. Use a conversation those accounts share. Both accounts must meet the normal profile requirements.

1. Start a Voice call and allow microphone access. Receiver opens the site and accepts.
2. Confirm a spoken sentence is heard in BOTH directions. Use headphones to avoid acoustic feedback when testing on one computer.
3. Test mute/unmute, device selection, navigation, decline, and end.
4. Close the receiver's tab during a connected call; verify the caller sees reconnect/end instead of endless Connected.
5. Deny microphone access; verify there is a useful error and no invitation is sent.

A phone on Wi-Fi cannot use a laptop's `localhost` URL. Test actual phones with the public HTTPS/WSS deployment below. An HTTP LAN IP generally cannot access the microphone.

Useful local commands:

```bash
docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production --profile calls up -d livekit
docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production exec -T api python -m trustlens_api.modules.calling.doctor
```

The doctor checks authenticated room creation and deletion only. It does not prove browser audio, NAT traversal or TURN connectivity.

## Public deployment

Use the [official LiveKit VM deployment generator](https://docs.livekit.io/transport/self-hosting/vm/). It provides Caddy with automatic TLS, LiveKit's embedded TURN, and Docker Compose. Use a dedicated Linux media host/IP for this initial deployment; do not let its Caddy compete with an existing web proxy for port 443. The generated configuration can be migrated later.

On a machine with Docker, in a new PRIVATE directory:

```bash
docker pull livekit/generate
docker run --rm -it -v "$PWD:/output" livekit/generate
```

Follow the generator for your real domains, for example `rtc.your-domain.com` and `turn.your-domain.com`. Choose the VM setup, without Ingress, Egress or SIP: live calls do not need recording or telephony services. Deploy its generated configuration/startup script to the media host as described in the official guide. Before starting, pin the LiveKit server image to `livekit/livekit-server:v1.13.9` and merge this setting into the existing `livekit.yaml` (do not create duplicate YAML keys):

```yaml
room:
  auto_create: false
```

TrustLens creates rooms through its authenticated API before granting access. Disabling automatic room creation prevents an old join token from recreating a closed room.

Set BOTH RTC and TURN DNS records to the media host public IP (DNS only, no ordinary HTTP CDN proxy). Permit 80/TCP for certificate issuance, 443/TCP for WSS and TURN/TLS, 7881/TCP for ICE TCP, 3478/UDP for TURN UDP and the generated RTC UDP range, normally 50000–60000. Preserve the generator's Caddy layer-4 routing: it shares 443 between signaling and TURN/TLS by hostname. Match firewall rules to the actual generated config. See [official port guidance](https://docs.livekit.io/transport/self-hosting/ports-firewall/).

In TrustLens's private deployment environment set:

```dotenv
CALLS_ENABLED=true
CALLS_LIVEKIT_URL=wss://rtc.your-domain.com
CALLS_LIVEKIT_INTERNAL_URL=https://rtc.your-domain.com
CALLS_LIVEKIT_API_KEY=<the key in your generated LiveKit config>
CALLS_LIVEKIT_API_SECRET=<the matching secret, at least 32 characters>
```

The public URL is delivered at runtime by the authenticated call API. Never use `NEXT_PUBLIC_` for API secrets. `CALLS_LIVEKIT_INTERNAL_URL` may instead be a private reachable HTTP service URL. Frontend HTTPS, API HTTPS, existing CORS/trusted-host settings and migration `202610140100` must also be correct. Restart/recreate API workers after changing environment. The `prod` and `hosted` Compose files now forward these variables. Do not start the localhost `calls` profile on the public server when using the dedicated media host.

Do not simply copy localhost media config to production: it advertises 127.0.0.1 and has no public TLS/TURN setup. The backend and frontend code need no calling-specific rewrite for deployment.

Before launch, verify Wi-Fi↔mobile-data audio, microphone denial, screen lock/background behavior, brief network interruptions and a restrictive network requiring TURN/TLS. Confirm the selected relay transport in browser WebRTC diagnostics. The local doctor cannot certify this. Mobile power saving, browser permissions and network loss can still interrupt calls.

## Optional browser notifications

Web Push is an invitation fallback, not a native VoIP calling system. It requires a public HTTPS site (localhost may be used for compatible development browsers), a service worker, permission and VAPID credentials. iPhone/iPad web push requires a supported OS and adding the web app to the Home Screen; it is not a universal background browser feature. Force-stopped browsers, disabled notifications, Do Not Disturb, battery restrictions and offline devices can prevent or delay delivery. Native Android/iOS call integration remains future work.

For localhost, generate keys using the existing API image with the repository mounted (replace the contact with your real one):

```bash
MSYS_NO_PATHCONV=1 docker run --rm --user 0 --network none --mount "type=bind,source=$(pwd -W),target=/workspace" --entrypoint python trustlens-api:latest /workspace/scripts/configure_calls.py --root /workspace --push-subject mailto:operations@your-domain.com
docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production up -d --no-deps api
```

On Linux, use `pwd` instead of `pwd -W`. For public deployment generate VAPID keys using `python -m py_vapid --gen` in a private directory, then `python -m py_vapid --applicationServerKey`. Set `CALLS_VAPID_PUBLIC_KEY` to the application-server key; set `CALLS_VAPID_PRIVATE_KEY` to the base64url DER-encoded private key (or a readable private-key path inside the API container), and `CALLS_VAPID_SUBJECT` to a real `mailto:` contact. Preserve those keys across restarts. The local generator creates the correct DER encoding automatically; it deliberately refuses public calling configuration to avoid replacing it with localhost values.

Users click Enable Call Alerts. The service worker caches no chat bodies/audio/tokens. Push payloads use generic wording, opaque call/conversation IDs and a timestamp. Saved subscriptions are encrypted server-side. Switching accounts uses a fresh browser subscription; log out to unsubscribe on a shared device.

## Backend and operations

All endpoints require an active account and conversation membership; only the owning browser device may control an accepted call. Join grants expire quickly, are scoped to one room/device and allow microphone publishing only. Sorted PostgreSQL transaction locks prevent simultaneous call starts across API workers. API worker maintenance expires calls, sends optional push and removes ended media rooms. If API workers are unavailable, clients stop on a bounded timeout; an abandoned room also has idle/departure timeouts.

Completed call records cannot be updated, deleted or truncated through ordinary SQL application access. `chat_audit` preserves lifecycle transitions. `chat_call_runtime` holds cleanup progress and latest client-reported byte/quality counters, which are diagnostics rather than independently verified evidence. Chat archive export includes call records and runtime state. Continue encrypted database and object backups with an independent backup destination; retain the encryption keys securely. A database administrator can still change/drop schema, so triggers are not a substitute for backups and access controls.

LiveKit uses encrypted WebRTC transport. This implementation does NOT claim end-to-end encryption through the SFU. No Egress recorder is installed and no call audio is saved by TrustLens. Deployment operators must protect the media host and secrets.

Set `CALLS_ENABLED=false` and recreate API workers to disable new calls. Keep media credentials while maintenance closes existing rooms. Stop LiveKit as well for immediate media shutdown. Do not downgrade the retention migrations. Installer recovery restores prior application images and source where safe while leaving additive schema/records intact; if the original pre-retention application would expose hidden chat data, recovery stops and requires a forward fix.

## Future paid migration

LiveKit Cloud is the least-disruptive managed option because the existing client SDK, room grants and room-service API remain compatible. Move the public/internal URLs and API credentials to the managed project, review its room/token semantics, re-run the network and permission tests, and configure provider monitoring/billing. No paid account has been created here. Managed media still cannot make a force-stopped browser receive native incoming calls.
