import Link from 'next/link';

export const metadata = {
  title: 'Community Guidelines · TrustLens',
  description: 'What is and is not allowed when buying, selling, and messaging on TrustLens.',
};

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
    <section id={id} className="scroll-mt-24 border-t border-border/60 pt-8">
      <h2 className="text-lg font-bold tracking-tight">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

export default function CommunityGuidelinesPage() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8">
      <header>
        <p className="text-sm font-medium text-brand">Community Guidelines</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">
          How TrustLens expects people to behave
        </h1>
        <p className="mt-3 text-muted-foreground">
          These apply to every listing, message, and profile on TrustLens. They exist so that the
          Trust Score on a seller&apos;s profile means something - a verified account that then
          breaks these rules loses that trust the same way an unverified one never had it.
        </p>
      </header>

      <div className="mt-8 space-y-8">
        <Section id="listings" title="1. Listings must be genuine">
          <ul className="list-inside list-disc space-y-1">
            <li>List items you actually have and intend to sell, at a real price.</li>
            <li>
              Use your own photos of the actual item, not stock images or someone else&apos;s.
            </li>
            <li>
              Describe condition, defects, and anything a buyer would reasonably want to know before
              agreeing to buy.
            </li>
            <li>No prohibited, stolen, counterfeit, or illegal items, under any category.</li>
          </ul>
        </Section>

        <Section id="messaging" title="2. Messaging must stay respectful and on-platform">
          <ul className="list-inside list-disc space-y-1">
            <li>
              No harassment, threats, hate speech, or discriminatory language toward another user.
            </li>
            <li>
              No pressuring another user to move off-platform before basic details are agreed, and
              no requesting an OTP, password, or verification code from anyone.
            </li>
            <li>No spam, repeated unsolicited messages, or advertising unrelated to a listing.</li>
          </ul>
        </Section>

        <Section id="fraud" title="3. No fraud, scam patterns, or advance-payment pressure">
          <p>
            Listings and messages are screened for scam-pattern language (urgency pressure,
            advance-fee requests, and similar patterns), and accounts engaged in this behavior are
            removed. See{' '}
            <Link href="/safety" className="text-primary underline-offset-4 hover:underline">
              Safety
            </Link>{' '}
            for what this looks like from a buyer&apos;s side.
          </p>
        </Section>

        <Section id="one-account" title="4. One identity, one account">
          <p>
            Identity verification exists so a Trust Score is tied to a real, consistent person or
            business. Creating multiple accounts to evade a ban, manipulate a score, or misrepresent
            who is selling is a violation on its own, independent of anything else done with those
            accounts.
          </p>
        </Section>

        <Section id="consequences" title="5. What happens when these are broken">
          <p>
            Depending on severity: a listing can be removed, an account can be flagged for manual
            review, a Trust Score can be capped regardless of other checks passed, or an account can
            be suspended. A seller can appeal a specific decision from their dashboard - see{' '}
            <Link href="/help" className="text-primary underline-offset-4 hover:underline">
              Help
            </Link>
            .
          </p>
        </Section>

        <Section id="reporting" title="6. Reporting a violation">
          <p>
            If you see a listing or message that breaks these guidelines,{' '}
            <Link href="/report-issue" className="text-primary underline-offset-4 hover:underline">
              report it
            </Link>
            . Reports are reviewed by staff, not resolved automatically.
          </p>
        </Section>
      </div>
    </main>
  );
}
