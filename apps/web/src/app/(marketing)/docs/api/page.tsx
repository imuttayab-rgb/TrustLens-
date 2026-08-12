import Link from 'next/link';

export const metadata = {
  title: 'Public API · TrustLens',
  description:
    'Read a seller Trust Score from your marketplace: authentication, the score response, signature verification and webhooks.',
};

/**
 * Integration guide for the public Trust Score API (P6-06).
 *
 * Written for the engineer at a marketplace who has been handed a key and an
 * afternoon. The order is the order they will need things: authenticate, read
 * a score, understand what came back, prove it is ours, get told when it
 * changes.
 *
 * Every example is a real request/response taken from a running instance, not
 * an idealised one - including the awkward parts (`unavailableSignals`, a
 * capped score), because those are what an integrator hits on day two and
 * would otherwise assume were bugs.
 */

function Code({ children }: { children: React.ReactNode }) {
  return (
    <pre className="mt-3 overflow-x-auto rounded-lg border border-border/70 bg-card/60 p-4 text-xs leading-relaxed">
      <code className="font-mono">{children}</code>
    </pre>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24 border-t border-border/60 pt-10">
      <h2 className="text-xl font-bold tracking-tight">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

const CONTENTS = [
  ['authentication', 'Authentication'],
  ['read-a-score', 'Read a score'],
  ['what-you-get', 'Reading the response'],
  ['verify', 'Verifying a response is ours'],
  ['batch', 'Looking up many sellers'],
  ['webhooks', 'Webhooks'],
  ['limits', 'Rate limits and quota'],
  ['errors', 'Errors'],
] as const;

export default function PublicApiDocsPage() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8">
      <header>
        <p className="text-sm font-medium text-brand">Public API · v1</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">
          Read a seller&apos;s Trust Score from your marketplace
        </h1>
        <p className="mt-3 text-muted-foreground">
          One authenticated GET returns a 0–100 score, a risk band, and the reasons behind it. The
          score covers sellers <strong>enrolled with TrustLens</strong>; anyone else returns 404,
          which means &ldquo;no record&rdquo;, not &ldquo;safe&rdquo;.
        </p>
      </header>

      <nav aria-label="Contents" className="mt-8 rounded-lg border border-border/70 bg-card/40 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Contents
        </p>
        <ol className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
          {CONTENTS.map(([id, label]) => (
            <li key={id}>
              <a href={`#${id}`} className="text-brand hover:underline">
                {label}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className="mt-10 space-y-10">
        <Section id="authentication" title="Authentication">
          <p>
            Every request carries your API key as a bearer token. Keys look like{' '}
            <code className="font-mono text-xs">tl_live_a1b2c3d4e5.&lt;secret&gt;</code> — the part
            before the dot identifies the key, the part after is the secret.
          </p>
          <Code>{`curl https://api.trustlens.app/public/v1/sellers/quick-deals-pk/trust-score \\
  -H "Authorization: Bearer tl_live_a1b2c3d4e5.YOUR_SECRET_HERE"`}</Code>
          <p>
            The secret is shown once, when the key is issued, and is stored only as a hash. If you
            lose it, ask for a <strong>rotation</strong> rather than a copy: rotation issues a new
            key and keeps the old one working for 24 hours, so you can redeploy without an outage.
            If a key leaks, ask for a <strong>revocation</strong> instead — that takes effect
            immediately and returns <code className="font-mono text-xs">410</code> on the next call.
          </p>
          <p>
            Keep the key server-side. It is not scoped to an origin, so a key in browser JavaScript
            is a key anyone can read and spend your quota with.
          </p>
        </Section>

        <Section id="read-a-score" title="Read a score">
          <p>
            <code className="font-mono text-xs">
              GET /public/v1/sellers/&#123;sellerRef&#125;/trust-score
            </code>
          </p>
          <p>
            <code className="font-mono text-xs">sellerRef</code> may be a TrustLens id, the
            seller&apos;s handle, or{' '}
            <code className="font-mono text-xs">&#123;yourSlug&#125;:&#123;yourSellerId&#125;</code>{' '}
            if you enrolled the seller through this API — so you can look up by the id you already
            hold, without storing ours.
          </p>
          <Code>{`{
  "sellerRef": "quick-deals-pk",
  "score": 25,
  "riskLevel": "HIGH",
  "riskLabel": "High risk",
  "confidence": 0.76,
  "verifications": {
    "identity": "REJECTED",
    "phone": "VERIFIED",
    "email": "VERIFIED"
  },
  "reasons": [
    {
      "code": "PHONE_LINE_TYPE_VOIP",
      "impact": "NEGATIVE",
      "text": "The phone number is an internet (VOIP) number rather than a mobile SIM."
    },
    {
      "code": "IDENTITY_VERIFIED",
      "impact": "POSITIVE",
      "text": "A valid government ID was submitted and checked."
    }
  ],
  "unavailableSignals": ["LISTING_PRICE_REALISTIC"],
  "modelVersion": "v1.0",
  "computedAt": "2026-08-11T16:22:33.343960+00:00",
  "expiresAt": "2026-09-10T16:22:33.343960+00:00"
}`}</Code>
          <p>
            Responses are cached for five minutes and carry an{' '}
            <code className="font-mono text-xs">ETag</code>. Send it back as{' '}
            <code className="font-mono text-xs">If-None-Match</code> and an unchanged score costs
            you a <code className="font-mono text-xs">304</code> instead of a quota unit.
          </p>
        </Section>

        <Section id="what-you-get" title="Reading the response">
          <p>
            <strong>
              Switch on <code className="font-mono text-xs">code</code>, never on{' '}
              <code className="font-mono text-xs">text</code>.
            </strong>{' '}
            Reason codes are stable; the wording is written for buyers and will be reworded.
          </p>
          <p>
            <strong>
              <code className="font-mono text-xs">unavailableSignals</code> is not a list of
              failures.
            </strong>{' '}
            These are checks that could not be run — a provider was down, or the seller has no
            listings yet. They are excluded from the score rather than counted against the seller,
            which is why a score with several of them also has lower{' '}
            <code className="font-mono text-xs">confidence</code>. Treat low confidence as &ldquo;we
            do not know enough yet&rdquo;, not as a soft failure.
          </p>
          <p>
            <strong>
              <code className="font-mono text-xs">riskLevel</code> is derived from{' '}
              <code className="font-mono text-xs">score</code>
            </strong>{' '}
            at fixed boundaries: 0–39 HIGH, 40–69 MEDIUM, 70–100 LOW. Band on{' '}
            <code className="font-mono text-xs">riskLevel</code> rather than re-deriving it, so your
            thresholds cannot drift from ours.
          </p>
          <p>
            <strong>A 404 means &ldquo;no record&rdquo;, not &ldquo;fraudulent&rdquo;.</strong> Most
            sellers on your platform will not be enrolled. Showing &ldquo;not verified&rdquo; is
            honest; showing &ldquo;high risk&rdquo; is not.
          </p>
        </Section>

        <Section id="verify" title="Verifying a response is ours">
          <p>
            Every response is signed. A score is a claim about a person that money moves on, so if
            it reaches you through a proxy or a cache you do not control, the signature is what
            tells it apart from one an attacker wrote.
          </p>
          <Code>{`X-TrustLens-Signature: t=1786464719,v1=b5147c037807490b210adcc10b62c2b1...
X-TrustLens-Key-Id: s1`}</Code>
          <p>
            The signature is an HMAC-SHA256 over{' '}
            <code className="font-mono text-xs">&lt;timestamp&gt;.&lt;raw response body&gt;</code>,
            using the shared secret issued with your key. Verify against the{' '}
            <strong>bytes you received</strong>, before parsing — re-serialising the JSON first will
            change them and the check will fail.
          </p>
          <Code>{`import hmac, time
from hashlib import sha256

def verify(raw_body: bytes, header: str, secret: bytes, max_age=300) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(","))
    ts = int(parts["t"])

    # Reject replays: the timestamp is inside the signed material, so an old
    # response stays valid forever without this check.
    if abs(time.time() - ts) > max_age:
        return False

    expected = hmac.new(secret, f"{ts}.".encode() + raw_body, sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])`}</Code>
          <p>
            <code className="font-mono text-xs">X-TrustLens-Key-Id</code> names the signing key so
            it can be rotated without every partner breaking at the same instant. Keep accepting the
            previous key id for a short window when we announce a rotation.
          </p>
        </Section>

        <Section id="batch" title="Looking up many sellers">
          <p>
            <code className="font-mono text-xs">POST /public/v1/sellers/lookup</code> takes up to 50
            references and counts as one request against your rate limit. Use it for a search
            results page rather than 50 individual calls.
          </p>
          <Code>{`{ "sellerRefs": ["quick-deals-pk", "bilal-motors", "not-enrolled"] }

→ {
  "results": [
    { "sellerRef": "quick-deals-pk", "score": 25, "riskLevel": "HIGH", ... },
    { "sellerRef": "bilal-motors",  "score": 25, "riskLevel": "HIGH", ... }
  ],
  "notFound": ["not-enrolled"]
}`}</Code>
          <p>
            Unknown references come back in <code className="font-mono text-xs">notFound</code>{' '}
            rather than failing the whole call, so one unenrolled seller does not cost you the other
            49.
          </p>
        </Section>

        <Section id="webhooks" title="Webhooks">
          <p>
            Rather than polling, register an endpoint and we will POST when a score changes. Events:{' '}
            <code className="font-mono text-xs">SCORE_UPDATED</code>,{' '}
            <code className="font-mono text-xs">SELLER_VERIFIED</code>,{' '}
            <code className="font-mono text-xs">SELLER_FLAGGED</code>,{' '}
            <code className="font-mono text-xs">APPEAL_RESOLVED</code>.
          </p>
          <Code>{`POST https://your-app.example/trustlens-hook
X-TrustLens-Event: SCORE_UPDATED
X-TrustLens-Delivery: 019ff5c5-d95c-76b3-a092-77ecebf98cc5
X-TrustLens-Signature: t=1786464719,v1=...

{
  "seller_id": "3a8f4d2c-8443-5ead-a6ff-415a3ec75718",
  "score": 25,
  "previous_score": 40,
  "delta": -15,
  "risk_level": "HIGH",
  "trigger": "APPEAL_RESOLUTION",
  "model_version": "v1.0"
}`}</Code>
          <p>
            The signature scheme is identical to the one above, so you can reuse the same
            verification function — with your webhook secret rather than your API secret.
          </p>
          <p>
            <strong>Answer with any 2xx.</strong> Anything else is retried with exponential backoff
            — 30s, 1m, 2m, 4m — and then given up on. Reply quickly and do the work afterwards; a
            slow handler will time out at 10 seconds and be retried, which is how duplicates happen.
          </p>
          <p>
            <strong>Expect duplicates.</strong> Delivery is at-least-once, so the same{' '}
            <code className="font-mono text-xs">X-TrustLens-Delivery</code> id can arrive twice.
            Treat that header as an idempotency key.
          </p>
        </Section>

        <Section id="limits" title="Rate limits and quota">
          <p>
            Free-tier keys are limited per minute and to a monthly quota; partner-tier keys get a
            higher ceiling. Both are reported on every response:
          </p>
          <Code>{`X-RateLimit-Limit: 60
X-RateLimit-Remaining: 57
X-RateLimit-Reset: 1786464780`}</Code>
          <p>
            Exceeding the per-minute limit returns <code className="font-mono text-xs">429</code>{' '}
            with a <code className="font-mono text-xs">Retry-After</code> header. Exhausting the
            monthly quota also returns <code className="font-mono text-xs">429</code>, with a code
            of <code className="font-mono text-xs">QUOTA_EXCEEDED</code> — the difference matters,
            because waiting will not fix the second one.
          </p>
        </Section>

        <Section id="errors" title="Errors">
          <p>
            Errors are RFC 9457 problem documents. Switch on{' '}
            <code className="font-mono text-xs">code</code>, and quote{' '}
            <code className="font-mono text-xs">requestId</code> when you ask us about one.
          </p>
          <Code>{`{
  "type": "https://api.trustlens.app/errors/not-found",
  "title": "Not found",
  "status": 404,
  "code": "NOT_FOUND",
  "detail": "No enrolled seller matches that reference.",
  "requestId": "req_356e5336ef844d1ca5a7"
}`}</Code>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              <code className="font-mono text-xs">401 API_KEY_INVALID</code> — missing or malformed
              key.
            </li>
            <li>
              <code className="font-mono text-xs">410 API_KEY_REVOKED</code> — the key was revoked
              or expired. Rotating will not help; ask for a new one.
            </li>
            <li>
              <code className="font-mono text-xs">403 SCOPE_MISSING</code> — the key is valid but
              was not granted this scope.
            </li>
            <li>
              <code className="font-mono text-xs">404 NOT_FOUND</code> — no enrolled seller. Not a
              judgement about them.
            </li>
            <li>
              <code className="font-mono text-xs">429</code> — rate limit or monthly quota.
            </li>
          </ul>
        </Section>
      </div>

      <footer className="mt-12 border-t border-border/60 pt-6 text-sm text-muted-foreground">
        <p>
          A Postman collection covering every endpoint ships with the repository at{' '}
          <code className="font-mono text-xs">docs/api/trustlens.postman_collection.json</code>.
        </p>
        <p className="mt-2">
          <Link href="/check" className="text-brand hover:underline">
            Try a lookup without a key →
          </Link>
        </p>
      </footer>
    </main>
  );
}
