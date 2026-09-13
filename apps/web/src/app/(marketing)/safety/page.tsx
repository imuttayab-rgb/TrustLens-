import Link from 'next/link';

export const metadata = {
  title: 'Safety Tips · TrustLens',
  description:
    'How to buy and sell safely on TrustLens, and what a Trust Score does and does not promise.',
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

export default function SafetyPage() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8">
      <header>
        <p className="text-sm font-medium text-brand">Safety</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Buying and selling safely</h1>
        <p className="mt-3 text-muted-foreground">
          A Trust Score tells you which checks a seller has completed - it is not a guarantee of
          physical safety, and TrustLens does not make that guarantee. The habits below matter
          regardless of how high a score is.
        </p>
      </header>

      <div className="mt-8 space-y-8">
        <Section id="inspect-first" title="1. Inspect before you pay">
          <p>
            See the item in person, check it works as described, and only pay once you&apos;re
            satisfied - for any price, from any seller. A high Trust Score means checks were
            completed, not that this specific item is exactly as described.
          </p>
        </Section>

        <Section id="no-advance-payment" title="2. Never send an advance payment">
          <p>
            &quot;Send a deposit to hold it&quot; or &quot;pay now, courier will deliver&quot; are
            the two most common patterns in real scam reports. A genuine local seller selling a
            physical item has no reason to need money before you&apos;ve seen it.
          </p>
        </Section>

        <Section id="otp" title="3. Never share an OTP or verification code with anyone">
          <p>
            TrustLens, a legitimate seller, or a legitimate buyer will never ask you to read them a
            one-time code over chat or a phone call. Anyone who asks is trying to take over an
            account - yours or someone else&apos;s.
          </p>
        </Section>

        <Section id="in-app-chat" title="4. Keep the conversation in TrustLens chat">
          <p>
            Messaging inside the platform keeps a record if something goes wrong later, and lets you
            report a conversation directly. Being pushed to WhatsApp or a phone call immediately,
            before any details are agreed, is a common pressure tactic - it is fine to say no.
          </p>
        </Section>

        <Section id="meet-publicly" title="5. Meet in a public, well-lit place">
          <p>
            A busy market, a shopping center, or a bank branch during opening hours are all better
            choices than a private residence for a first meeting with someone you don&apos;t know.
            Bring a friend if you can, and let someone know where you&apos;re going.
          </p>
        </Section>

        <Section id="what-score-means" title="6. What a Trust Score does and doesn't mean">
          <p>
            The score reflects which checks a seller has completed: identity document plausibility,
            a selfie face-match, phone verification, email verification, and a scan of their
            listings for scam-pattern language. It is not a government identity check, not a
            criminal-background check, and not a promise about any single transaction. See{' '}
            <Link href="/help" className="text-primary underline-offset-4 hover:underline">
              Help
            </Link>{' '}
            for how the score is built.
          </p>
        </Section>

        <Section id="report" title="7. If something feels wrong">
          <p>
            Trust that feeling. Stop the conversation, and{' '}
            <Link href="/report-issue" className="text-primary underline-offset-4 hover:underline">
              report the listing or seller
            </Link>{' '}
            so staff can look into it - reporting doesn&apos;t require you to have lost anything
            first.
          </p>
        </Section>
      </div>
    </main>
  );
}
