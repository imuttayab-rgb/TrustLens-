# Setting up the external accounts

Four optional integrations. **The system works today without any of them** —
email goes to a local inbox, OTPs print to the worker log, and VPN detection
falls back to offline heuristics. Set these up only when you want the real
thing.

Do them in this order. The first is the only one that really matters for a
demo; the rest are polish.

|                   | What it buys you         | Time              | Cost            |
| ----------------- | ------------------------ | ----------------- | --------------- |
| 1. Resend         | Real verification emails | 30 min + DNS wait | Free (3,000/mo) |
| 2. IPQualityScore | Real VPN/proxy detection | 10 min            | Free (5,000/mo) |
| 3. Twilio         | Real SMS OTP             | 20 min            | Trial credit    |
| 4. A public host  | Public URLs              | 1–2 hours         | $0–5/mo         |

After each one: edit `.env.production`, then `make prod-restart`.

---

## 1. Resend — real email (P8-01, P8-02)

**Why bother.** Right now every verification email lands in Mailpit at
http://localhost:8025 and never leaves the machine. Fine for a demo you drive
yourself; useless if a supervisor wants to register from their own laptop.

**You need a domain.** Resend will not send from `gmail.com` — you have to own
the sending domain. A `.com` is about $10/year from Namecheap or Cloudflare. If
you do not have one, skip this whole section; Mailpit is a legitimate demo
setup and the report can say so.

### Step by step

1. Sign up at **resend.com** — free tier, no card.
2. **Domains → Add Domain**, enter your domain (e.g. `trustlens.pk`).
3. Resend shows you **three DNS records**. Add all three at your registrar:

   | Type         | What it is | Why                                              |
   | ------------ | ---------- | ------------------------------------------------ |
   | `MX` + `TXT` | SPF        | says which servers may send as you               |
   | `TXT`        | DKIM       | signs each message so it cannot be forged        |
   | `TXT`        | DMARC      | tells receivers what to do if the first two fail |

   In Cloudflare DNS: **DNS → Records → Add record**, paste name and value
   exactly. Set proxy status to **DNS only** (grey cloud), not proxied.

4. Click **Verify**. It usually takes 5–30 minutes; occasionally a few hours.
5. **API Keys → Create API Key**, permission _Sending access_. Copy it — it is
   shown once.
6. Edit `.env.production`:

   ```
   EMAIL_PROVIDER=resend
   RESEND_API_KEY=re_xxxxxxxxxxxx
   EMAIL_FROM=no-reply@yourdomain.com
   EMAIL_FROM_NAME=TrustLens
   ```

7. `make prod-restart`

### Test it properly

Register with a **Gmail** address, then an **Outlook** one, then a **Yahoo**
one. Check the inbox _and the spam folder_ for each.

This is not optional fussing. Without correct SPF, DKIM and DMARC the mail is
_accepted_ and then silently filed as spam — so signup appears to work, no
error is logged anywhere, and users simply never arrive. It is the single
most common way an email integration "works" and doesn't.

If a message lands in spam, your DNS records are wrong or not yet propagated.
Paste the raw message headers into **mail-tester.com** and it will tell you
which of the three failed.

### Do not skip DMARC

SPF and DKIM alone leave the domain spoofable. Start permissive and tighten:

```
_dmarc.yourdomain.com   TXT   v=DMARC1; p=none; rua=mailto:you@yourdomain.com
```

`p=none` only reports. Once a week of reports looks clean, change to
`p=quarantine`.

---

## 2. IPQualityScore — VPN and proxy detection (P8-04)

**Note the provider names.** The code accepts `ipqualityscore`, `ipapi` or
`offline` — an earlier plan document mentioned proxycheck.io and vpnapi.io,
which are _not_ implemented. Use one of the three above.

1. Sign up at **ipqualityscore.com** — free tier, 5,000 lookups/month.
2. **Settings → Account → API Keys**, copy the private key.
3. Edit `.env.production`:

   ```
   IP_INTEL_PROVIDER=ipqualityscore
   IP_INTEL_API_KEY=your_key_here
   ```

4. `make prod-restart`

Results are cached for 24 hours, so 5,000 lookups goes a long way.

**It fails open by design.** If the provider is slow or down, the check returns
the offline result rather than raising. That is deliberate: a VPN signal that
fails _closed_ would cost a seller points because _our_ provider had an outage,
on something they cannot appeal because they did nothing wrong.

**Say this in the report:** a VPN is not evidence of fraud. Plenty of honest
people in Pakistan use one. It is one weak signal among many, and it is
weighted as such.

---

## 3. Twilio — real SMS OTP (P8-03)

**Read this before spending time.** Sending SMS to Pakistani numbers at any
real volume requires **PTA registration and a per-carrier sender ID against an
NTN** — a business registration process, not something you can do in an
afternoon. A Twilio trial works for a demo and nothing more.

That constraint belongs in the report as a _deployment limitation_, not a
defect. Email OTP is the primary channel and always was.

1. Sign up at **twilio.com/try-twilio**. You get trial credit (~$15).
2. Verify your own mobile number when asked. **On a trial account you can only
   send to numbers you have verified** — so verify every phone you plan to use
   in the demo, in advance.
3. From the Console dashboard copy **Account SID** and **Auth Token**.
4. **Phone Numbers → Buy a number** with SMS capability. A US number is
   cheapest and works for a demo.
5. Edit `.env.production`:

   ```
   SMS_PROVIDER=twilio
   TWILIO_ACCOUNT_SID=ACxxxxxxxx
   TWILIO_AUTH_TOKEN=your_token
   TWILIO_FROM_NUMBER=+15551234567
   ```

6. `make prod-restart`

**Leave it on `console` for development.** The OTP prints to the worker log
(`make prod-logs`), which is faster to work with and costs nothing.

Trial messages arrive with a "Sent from a Twilio trial account" prefix. You
cannot remove it without upgrading. Mention it before the demo so nobody thinks
it is a bug.

---

## 4. Neon (database) + Vercel (frontends)

This is the split you asked for. **One thing to be clear about first:** it does
not remove the need for a server.

| Piece            | Where                      | Why                    |
| ---------------- | -------------------------- | ---------------------- |
| web, admin       | **Vercel**                 | Next.js, native builds |
| Postgres         | **Neon**                   | managed, free tier     |
| **api + worker** | **a small host**           | ← still yours          |
| Redis, storage   | that host, or Upstash / R2 | either                 |

Vercel runs functions, not processes. The worker is an always-on consumer
holding ~323 MB of OCR and face-matching models, taking ~2 seconds a document —
there is nothing on Vercel to put it in. So one 512 MB instance remains,
roughly **$3–4/month**, and it is the only thing in this whole project that
costs money.

Everything below is prepared already: `apps/web/vercel.json`,
`apps/admin/vercel.json`, `docker/compose/docker-compose.hosted.yml`, and
`.env.hosted.example`.

---

### 4a. Neon

1. Sign up at **neon.tech** (free, no card). Create project `trustlens`,
   region closest to you — Singapore or Frankfurt from Pakistan.
2. **Connection Details** → copy the connection string.
3. `make hosted-init` — creates `.env.hosted` with real secrets.
4. Open `.env.hosted` and set the two database URLs. **They are not the same
   string**, and this is the step everyone gets wrong:

   ```
   # asyncpg. NO sslmode - asyncpg rejects that parameter outright.
   DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/trustlens

   # psycopg. MUST have sslmode - Alembic uses this URL verbatim and
   # nothing injects TLS into it.
   DATABASE_URL_SYNC=postgresql+psycopg://user:pass@ep-xxx.neon.tech/trustlens?sslmode=require

   DB_SSL_REQUIRE=true
   ```

   Paste Neon's URL unchanged into both and you get a connection error naming
   neither the parameter nor the driver — it reads as "the database is down".
   The app now **refuses to start** and tells you which URL is wrong instead.

5. `make hosted-migrate` — creates all 41 tables on Neon and seeds reference data.
6. `make hosted-up` — starts api + worker + redis against Neon.

**Two Neon free-tier behaviours to plan for, not discover:**

- **It sleeps after 5 minutes idle.** The first request then takes 3–5 seconds.
  Open the site once before a demo; do not let the examiner's first click be
  the wake-up call.
- **It closes idle connections.** `.env.hosted` already sets a small pool
  (`DB_POOL_SIZE=5`) that recycles every 5 minutes, which survives that. A
  large pool just sits holding dead handles.

---

### 4b. Vercel

Two projects from one repository — one per app.

1. Sign up at **vercel.com** with GitHub.
2. **Add New → Project** → import the repo.
3. For the **seller app**:
   - **Root Directory**: `apps/web`
   - Framework preset: Next.js (detected)
   - Leave build and install commands alone — `apps/web/vercel.json` already
     sets them to build through the workspace, which a bare `next build`
     cannot do here because the app imports five shared packages.
   - **Environment Variables**:
     ```
     NEXT_PUBLIC_API_BASE_URL = https://api.yourdomain.com
     API_BASE_URL_INTERNAL    = https://api.yourdomain.com
     ```
4. **Deploy**.
5. Repeat for the **admin app**, changing only **Root Directory** to
   `apps/admin`.

**`API_BASE_URL_INTERNAL` is the public URL here, not a container name.**
Locally it is `http://api:8000` because both run on one Docker network. Vercel
has no private route to your box, so server-rendered pages must go over the
internet like everyone else.

**`NEXT_PUBLIC_*` is compiled into the browser bundle.** Changing it needs a
**redeploy**, not a restart. This catches everyone exactly once.

---

### 4c. Join them up

Back in `.env.hosted`, fill in the real addresses and `make hosted-up` again:

```
API_BASE_URL=https://api.yourdomain.com
WEB_BASE_URL=https://trustlens-web.vercel.app
ADMIN_BASE_URL=https://trustlens-admin.vercel.app
SECURITY_JWT_ISSUER=https://api.yourdomain.com

SECURITY_CORS_ORIGINS=https://trustlens-web.vercel.app,https://trustlens-admin.vercel.app
SECURITY_TRUSTED_HOSTS=api.yourdomain.com,localhost,127.0.0.1
SECURITY_TRUSTED_PROXY_COUNT=1
```

**The last three are the ones that will waste your afternoon.** They are two
separate mechanisms and both fail silently in different ways:

- **`SECURITY_CORS_ORIGINS`** — the browser's `Origin`. Missing, and the
  browser blocks the call. The API log shows nothing wrong.
- **`SECURITY_TRUSTED_HOSTS`** — the request's `Host`. Missing, and the API
  answers **400 to everything** while every health check still reports
  healthy. I hit exactly this today with the container hostname.
- **`SECURITY_TRUSTED_PROXY_COUNT`** — set to 1 behind a proxy or load
  balancer, or every request appears to come from the proxy and rate limiting
  and the NETWORK signal both stop working. Too high and a client can spoof
  its own IP.

Set up **Resend first** (section 1). There is no Mailpit in this
configuration — nothing catches outbound mail, so without it verification
emails go nowhere at all.

### 4d. Check it

```bash
API_BASE_URL=https://api.yourdomain.com WEB_BASE_URL=https://trustlens-web.vercel.app   bash scripts/prod-check.sh

API_BASE_URL=https://api.yourdomain.com WEB_BASE_URL=https://trustlens-web.vercel.app   bash scripts/security-check.sh
```

Then the real thing: register → verify the email → become a seller → open the
public page from a phone on mobile data, not WiFi.

### 4e. Only then, ENV=production

Once TLS, real email and a real domain are all in place, set `ENV=production`.
That turns on a hardening validator which refuses to boot unless the database
uses TLS, the AI engines are real, API keys use the `tl_live` prefix, CORS is
an explicit allowlist, `DEBUG=false` and logs are JSON.

Let it fail and fix what it names. Do not weaken it — it is the check that
stops a development key reaching production.

---

## After any change

```bash
make prod-restart      # picks up .env.production
make prod-check        # 7 checks: is it actually serving
make prod-security     # 16 checks: is it actually safe
```

If something breaks, `RUNBOOK.md` §5 lists the faults that actually happen and
what to do about each.

---

## What to do if you set up none of this

Nothing breaks. You get:

- verification emails in the Mailpit inbox at http://localhost:8025
- OTP codes printed in `make prod-logs`
- VPN detection from offline heuristics
- the whole system on `localhost`

That is a complete, demonstrable product. Every one of these integrations is an
upgrade, not a dependency — which is deliberate, so the system cannot be broken
by an expired free tier six months after handover.
