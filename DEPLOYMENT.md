# Deployment

There are two ways to run TrustLens, and **the first one is the default**.

---

## Option A — run it yourself, anywhere (recommended)

The whole product runs in production mode from one compose file. No accounts,
no platform, no card. A laptop, a college server, a rented VPS — the same
command works on all of them.

```bash
make prod-init     # first time only: creates .env.production with real secrets
make prod-up       # build and start everything
make prod-check    # confirm it is actually serving
```

Windows: double-click **`prod-start.bat`**.

Day-to-day operation — starting, stopping, logs, backups, rollback, common
faults — is in **[`RUNBOOK.md`](RUNBOOK.md)**.

**Why this is the default.** The system is being handed to students who may
choose a host later, or never, and demo it from a laptop. Tying the project to
one platform's free tier would mean re-learning deployment the day that tier
changes its terms. A compose file does not expire.

### Putting it on the public internet

Same stack. Three changes:

1. Set every URL in `.env.production` to real `https://` hostnames, and make
   `SECURITY_CORS_ORIGINS` match.
2. Run `make prod-build` — `NEXT_PUBLIC_*` values are compiled into the browser
   bundle, so a restart is not enough.
3. Put a reverse proxy with TLS in front (Caddy is two lines; nginx works too).
   The containers speak plain HTTP on purpose — terminate TLS at the proxy.

### Moving one piece to a managed service

Every backing service is addressed only by a URL in `.env.production`. Change
it, stop the local container, done — no code change, no rebuild.

| Piece    | Change                                                     | Then                 |
| -------- | ---------------------------------------------------------- | -------------------- |
| Postgres | `DATABASE_URL`, `DATABASE_URL_SYNC`, `DB_SSL_REQUIRE=true` | `--scale postgres=0` |
| Redis    | `REDIS_URL`, `REDIS_QUEUE_URL`                             | `--scale redis=0`    |
| Storage  | `STORAGE_ENDPOINT_URL` + keys                              | `--scale minio=0`    |
| Email    | `EMAIL_PROVIDER=resend` + `RESEND_API_KEY`                 | `--scale mailpit=0`  |

Copy-paste values for Neon, Upstash, Cloudflare R2 and Resend are at the bottom
of `.env.production.example`.

**Sizing, measured rather than guessed:** the API image is 311 MB, the worker
1.16 GB, and the worker peaks at **323 MB RAM** with both AI engines resident.
That last number is the one that decides hosting — it does not fit a 256 MB
instance, so the worker needs 512 MB. Everything else is comfortable.

---

## Option B — the free-tier hosted setup, click by click

Everything below is one specific way to do Option A's "public internet" step,
using free tiers that existed in August 2026. It still works, and the research
in it is worth keeping — but it is **an example, not the plan**. Free tiers
change; the compose file does not.

Budget about **2 hours** the first time. Oracle is the slow part; everything
else is a few minutes each.

Each part ends with **"Save this"** — a value you copy somewhere safe.

---

## What goes where, and why

| Piece                    | Host                | Free? | Why this one                                                    |
| ------------------------ | ------------------- | ----- | --------------------------------------------------------------- |
| web + admin              | **Vercel**          | yes   | Next.js's own platform                                          |
| **API + worker + Redis** | **Oracle Cloud VM** | yes   | The only free host that runs a real always-on background worker |
| Postgres                 | **Neon**            | yes   | Managed, generous free tier                                     |
| Object storage           | **Cloudflare R2**   | yes   | Free egress, S3-compatible                                      |
| Email                    | **Resend**          | yes   | 3,000/month                                                     |
| Errors                   | **Sentry**          | yes   | 5,000 events/month                                              |

### Why not the platforms you would expect

Checked, and ruled out on evidence rather than taste:

- **Hugging Face Spaces** — twice disqualified. Docker Spaces now require a
  **PRO plan ($9/month)**, and Spaces block outbound traffic on ports above 1024. Postgres is 5432 and Redis is 6379. Neon has an HTTP driver so Postgres
  has a way round; **Redis does not** — ARQ speaks the Redis wire protocol and
  cannot run over Upstash's REST API. Our entire queue is ARQ, so the worker
  could not reach its own jobs even after paying.
- **Fly.io** — no free tier since 2024. New accounts get a 2-VM-hour trial.
- **Render** — the free tier explicitly excludes background workers.

Oracle is the one that works. It needs a card for identity verification (it is
not charged) and ARM capacity is often exhausted — see the retry note in Part 1.

---

## Part 0 — Before you start (5 min)

You need:

- A **credit/debit card** for Oracle's identity check. Not charged. If you do
  not have one, skip to _"The no-card route"_ at the end.
- A **GitHub account** with this repository pushed.
- A **domain** — optional but recommended. Without one, email lands in spam
  more often. A `.com` is ~$10/year. Everything works without it.

---

## Part 1 — Oracle Cloud VM (45–60 min, the hard part)

This one box runs the API, the worker and Redis.

### 1.1 Create the account

1. Go to **https://signup.cloud.oracle.com**
2. Country: **Pakistan**. Enter your name and email.
3. Verify the email, then set a password.
4. **Home Region — this cannot be changed later.** Choose a region with three
   availability domains, because ARM capacity is far easier to get:
   - **UK South (London)** ← recommended
   - or **Germany Central (Frankfurt)**

   Do **not** pick India West (Mumbai) — single AD, and permanently full.

5. Add the card when asked. You will see a temporary ~$1 authorisation that
   reverses. Confirm the account stays **"Always Free Eligible"**.
6. Wait for the "Your account is ready" email — 5 to 15 minutes.

### 1.2 Create the VM

1. Sign in at **https://cloud.oracle.com**
2. Hamburger menu (☰) → **Compute** → **Instances** → **Create instance**
3. **Name**: `trustlens`
4. **Image and shape** → **Edit**:
   - **Change image** → **Canonical Ubuntu** → **22.04**
     > ⚠️ Pick the plain image, **not** "Minimal". The minimal ARM image is
     > missing packages Docker needs.
   - **Change shape** → **Ampere** tab → **VM.Standard.A1.Flex**
   - **OCPUs: 2**, **Memory: 12 GB**
     > This is the whole Always Free ARM allowance. Oracle halved it from 4/24
     > in June 2026 without announcing it. 12 GB is far more than we need — the
     > worker peaks at 326 MB.
5. **Networking**: leave the defaults (it creates a VCN for you). Ensure
   **"Assign a public IPv4 address"** is **Yes**.
6. **Add SSH keys** → **Generate a key pair for me** → **download the private
   key**. Save it as `trustlens-key.pem` somewhere you will not lose it.
7. **Create**.

> **If you see "Out of host capacity"** — this is the single most common
> problem, and it is not something you did wrong. Options, in order:
>
> 1. Try again in a few hours. Capacity frees up constantly.
> 2. Try a different availability domain (AD-1, AD-2, AD-3) in the same region.
> 3. Reduce to 1 OCPU / 6 GB — still ample for us, and much easier to place.

**Save this:** the instance's **Public IP address**.

### 1.3 Open the firewall — both layers

Oracle blocks traffic in **two** independent places. People routinely fix one,
see it still failing, and assume the VM is broken.

**Layer 1 — the cloud security list:**

1. ☰ → **Networking** → **Virtual Cloud Networks** → click your VCN
2. **Security Lists** → **Default Security List**
3. **Add Ingress Rules**, and add these two:

   | Source CIDR | IP Protocol | Destination Port |
   | ----------- | ----------- | ---------------- |
   | `0.0.0.0/0` | TCP         | `80`             |
   | `0.0.0.0/0` | TCP         | `443`            |

**Layer 2 — the firewall on the machine itself.** Do this after you connect,
in step 1.4.

### 1.4 Connect and prepare the machine

From your laptop (Git Bash on Windows):

```bash
chmod 400 trustlens-key.pem
ssh -i trustlens-key.pem ubuntu@YOUR_PUBLIC_IP
```

Then, on the VM:

```bash
# Layer 2 of the firewall. Ubuntu on OCI ships iptables with a default DENY,
# and ufw is disabled - so `ufw allow` does nothing at all here.
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

# Docker
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin git
sudo usermod -aG docker ubuntu

# Swap. 12 GB is plenty, but the OCR spike is sharp and swap costs nothing.
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Log out and back in (`exit`, then ssh again) so the docker group applies.

```bash
docker run --rm hello-world   # must print "Hello from Docker!"
```

**Save this:** public IP, and the `trustlens-key.pem` file.

---

## Part 2 — Neon Postgres (5 min)

1. **https://neon.tech** → **Sign up** with GitHub
2. **Create project**:
   - Name: `trustlens`
   - Postgres version: **16**
   - Region: **Europe (Frankfurt)** — or whichever is nearest your Oracle region
3. On the dashboard, **Connection string** → copy it. It looks like:

   ```
   postgresql://user:PASSWORD@ep-xxx-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```

> ⚠️ **Two edits are required or the app will not start.**
>
> 1. **Delete `?sslmode=require`** from the end. Our driver is asyncpg, which
>    does not understand that parameter — TLS is switched on by
>    `DB_SSL_REQUIRE=true` instead.
> 2. You need the same URL **twice**, with different driver prefixes:
>
> ```
> DATABASE_URL=postgresql+asyncpg://user:PASSWORD@ep-xxx.neon.tech/neondb
> DATABASE_URL_SYNC=postgresql+psycopg://user:PASSWORD@ep-xxx.neon.tech/neondb
> ```
>
> The async one serves requests; the sync one runs migrations.

**Also note:** Neon's free tier **sleeps after 5 minutes idle**. The first
request after a quiet spell takes 3–5 seconds. Open the site once before your
demo starts — do not let the examiner's first click be the wake-up call.

**Save this:** both connection strings.

---

## Part 3 — Cloudflare R2 (10 min)

Holds CNIC images, selfies and listing photos.

1. **https://dash.cloudflare.com** → sign up
2. Left sidebar → **R2** → **Purchase R2** (it asks for a card; the free tier
   is 10 GB and we will use well under it)
3. **Create bucket** — do this three times:
   - `trustlens-documents`
   - `trustlens-listings`
   - `trustlens-models`
4. **Manage R2 API Tokens** → **Create API token**
   - Permissions: **Object Read & Write**
   - Scope to the three buckets above
   - **Create**
5. Copy the **Access Key ID**, **Secret Access Key**, and your
   **Account ID** (top right of the R2 page).

Your endpoint is:

```
https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

**Save this:** account ID, access key ID, secret access key.

---

## Part 4 — Resend email (10 min)

Verification emails, OTPs, appeal notifications.

1. **https://resend.com** → sign up with GitHub
2. **API Keys** → **Create API Key** → permission **Sending access** → copy it
   (shown once)
3. **Domains** → **Add Domain**:
   - **With a domain:** enter it, then add the DNS records Resend shows you
     (SPF, DKIM, DMARC) at your registrar. Wait for all three to go green.
   - **Without a domain:** skip this. You can send only to _your own_ signup
     address — fine for a demo you drive yourself, useless if the examiner
     wants to register their own account.

> Getting SPF/DKIM/DMARC right is what keeps verification emails out of spam.
> If they land in spam, signup silently breaks and nothing in the app reports an
> error — you would just see users never completing registration.

**Save this:** the API key, and the from-address (e.g. `no-reply@yourdomain.com`).

---

## Part 5 — Sentry (5 min, optional but do it)

1. **https://sentry.io** → sign up → **Create project** → platform **Python**
2. Copy the **DSN**.

Without this you find out the API is down when a person tells you.

**Save this:** the DSN.

---

## Part 6 — Vercel (10 min)

Hosts the two Next.js apps. Do this **after** the API is running, since it needs
the API's URL.

1. **https://vercel.com** → **Sign up with GitHub**
2. **Add New → Project** → import the `trustlens` repository
3. **This repo is a monorepo, so create TWO projects from it:**

   **Project 1 — the seller site**
   - Root Directory: `apps/web`
   - Framework: Next.js (detected)
   - Environment variables:
     ```
     NEXT_PUBLIC_API_BASE_URL = https://api.YOURDOMAIN.com
     NEXT_PUBLIC_ENV          = production
     ```

   **Project 2 — the admin panel**
   - Root Directory: `apps/admin`
   - Same two variables.

**Save this:** both deployed URLs.

---

## Part 7 — What to send me

Two rules, and the first one matters:

> ### 🔒 Do not paste secrets into this chat
>
> Anything in a chat message stays in the transcript. Put secrets **directly on
> the server**, where they are needed, and give me access to the machine
> instead. I will read them from `.env` there.

### Send me these — safe to paste

```
Oracle public IP    : 130.xx.xx.xx
Oracle region       : uk-london-1
Neon host           : ep-xxx-123456.eu-central-1.aws.neon.tech
R2 account ID       : abc123...
Domain (if any)     : trustlens.pk
Vercel web URL      : https://trustlens-web.vercel.app
Vercel admin URL    : https://trustlens-admin.vercel.app
Resend from address : no-reply@trustlens.pk
```

### Put these on the VM yourself — never in chat

SSH in, then:

```bash
mkdir -p ~/trustlens && cd ~/trustlens
nano .env.secrets
```

Paste, filling in your real values:

```bash
DATABASE_URL=postgresql+asyncpg://...
DATABASE_URL_SYNC=postgresql+psycopg://...
STORAGE_ACCESS_KEY_ID=...
STORAGE_SECRET_ACCESS_KEY=...
RESEND_API_KEY=...
SENTRY_DSN=...
```

Save with `Ctrl+O`, `Enter`, `Ctrl+X`. Then lock it down:

```bash
chmod 600 .env.secrets
```

### Give me access

Send the **contents of `trustlens-key.pem`** — the SSH private key — through
something that is not this chat. WhatsApp, or a password manager share.

Alternatively, add my key to the VM instead, which is better practice because
you can revoke it independently. Say the word and I will generate one.

---

## Part 8 — What I do once I have access

You do not need to do any of this; it is here so you can see it is not magic.

1. Generate the six production secrets with `scripts/generate-keys.sh` — JWT
   keypair, OTP pepper, token pepper, encryption key, response-signing secret.
2. Write the production `.env`. The app **refuses to start** in production
   unless all of these hold, which is deliberate:
   - `DEBUG=false`
   - `USE_FAKE_AI=false` ← real OCR and face matching
   - `DB_SSL_REQUIRE=true`
   - `SECURITY_API_KEY_PREFIX=tl_live`
   - `LOG_FORMAT=json`
   - `SECURITY_CORS_ORIGINS` an explicit allowlist, never `*`
3. Set `OCR_ENGINE=rapidocr` and `FACE_ENGINE=insightface` — the ONNX pair, so
   the worker runs in ~326 MB instead of ~2 GB.
4. Build and start API + worker + Redis with docker compose.
5. Run migrations, seed reference data **only** (never the demo seed — those are
   fake sellers with fake scores, and they must not exist in production).
6. Put Caddy in front for HTTPS with an automatic Let's Encrypt certificate.
7. Point `api.yourdomain.com` at the Oracle IP.
8. Redeploy Vercel with the real API URL.
9. Verify the whole journey against the live URLs: register → verify email →
   become a seller → upload CNIC → **real OCR runs** → score computed → public
   page renders → partner key reads a signed score → webhook fires.

---

## The no-card route

If you cannot use a card at all:

- Deploy **web + admin** to Vercel, **Postgres** to Neon, **Redis** to Upstash —
  none of these need a card.
- Run the **API and worker on your own laptop** during the demo, reachable
  through a Cloudflare Tunnel (free, no card).

The worker only pulls jobs from Redis; it needs no public address. This is a
legitimate topology rather than a hack, and it is honest to state in the report.
The cost is that the demo lives while your laptop does.

---

## Known rough edges

| Thing                   | What happens                               | What to do                                    |
| ----------------------- | ------------------------------------------ | --------------------------------------------- |
| Neon sleeps             | First request after 5 min idle takes 3–5 s | Open the site before the demo                 |
| Oracle capacity         | "Out of host capacity" on create           | Retry, change AD, or drop to 1 OCPU / 6 GB    |
| Worker cold start       | First OCR job after a restart takes ~4 s   | Normal — the model loads once                 |
| Email in spam           | Signup silently fails                      | Get SPF/DKIM/DMARC green before relying on it |
| `/seller/{handle}` 404s | The public buyer page                      | **Still unresolved (P0-12)** — see below      |

### One thing that must be decided before the demo

The public buyer page — `/seller/{handle}` — currently returns 404, because
`apps/web` holds no API key for the public endpoint. **This is the screen the
demo opens on.**

Two ways to fix it, and it is a design decision rather than a bug:

1. Issue the web app its own first-party server key.
2. Give the buyer page an internal authenticated route instead of going through
   the partner API.

I lean towards (2): the buyer page is not a partner, and giving it a partner key
means the most visible screen in the demo shares a credential path with third
parties. Tell me which you want and I will build it.
