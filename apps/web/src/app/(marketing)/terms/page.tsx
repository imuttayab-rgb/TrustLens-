/** Next.js route/layout composition for (marketing)/terms: page. */
import Link from 'next/link';

export const metadata = {
  title: 'Terms of Service · TrustLens',
  description: 'The terms every seller agrees to when creating a TrustLens account.',
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

export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8">
      <header>
        <p className="text-sm font-medium text-brand">Version 1.0</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Terms of Service</h1>
        <p className="mt-3 text-muted-foreground">
          These are the terms you accept when you create a TrustLens account. They cover what
          TrustLens does, what it does not do, and what is expected of you as a seller or buyer.
        </p>
      </header>

      <div className="mt-8 space-y-8">
        <Section id="what-trustlens-is" title="1. What TrustLens is">
          <p>
            TrustLens computes a Trust Score for sellers on the basis of identity, contact and
            listing checks that we run or that you complete. A score is a summary of completed
            checks, not a guarantee, an endorsement, or a legal certification of any seller&apos;s
            honesty.
          </p>
          <p>
            TrustLens is not a NADRA identity check and does not connect to any government database.
            Identity verification here means: does the submitted CNIC look genuine, and does the
            selfie match the photo on it. It is document plausibility and face matching, nothing
            more.
          </p>
        </Section>

        <Section id="your-account" title="2. Your account">
          <p>
            You must provide accurate information when registering, and keep your password
            confidential. You are responsible for activity under your account. Tell us immediately
            if you believe your account has been compromised.
          </p>
          <p>
            An account may be suspended or banned for submitting fraudulent identity documents,
            posting listings that violate the scam-pattern checks, or otherwise abusing the
            platform.
          </p>
        </Section>

        <Section id="listings" title="3. Listings">
          <p>
            You are responsible for the accuracy of every listing you post. Every listing is checked
            automatically for scam patterns; TrustLens may flag, hide, or remove a listing it
            assesses as high risk. A removed listing is kept on record so the score it contributed
            to can still be explained and, if you disagree, appealed.
          </p>
        </Section>

        <Section id="biometric-consent" title="4. Biometric data">
          <p>
            Identity verification compares a selfie against the photo on your CNIC, which is
            biometric processing. We ask for your explicit consent before running this check - see
            the{' '}
            <Link href="/privacy" className="text-primary underline-offset-4 hover:underline">
              Privacy Policy
            </Link>{' '}
            for how that data is stored, and for how long.
          </p>
        </Section>

        <Section id="no-warranty" title="5. No warranty">
          <p>
            TrustLens is provided &ldquo;as is&rdquo;. We do not guarantee that a high Trust Score
            means a transaction with that seller will go well, or that a low score means it will
            not. Always inspect goods before paying, and never send advance payment to someone you
            have not met in person.
          </p>
        </Section>

        <Section id="changes" title="6. Changes to these terms">
          <p>
            We may update these terms as the product changes. Material changes will be reflected in
            the version number at the top of this page, and continuing to use TrustLens after a
            change means you accept the update.
          </p>
        </Section>

        <Section id="contact" title="7. Contact">
          <p>
            Questions about these terms can be sent through the{' '}
            <Link href="/help" className="text-primary underline-offset-4 hover:underline">
              Help page
            </Link>
            .
          </p>
        </Section>
      </div>
    </main>
  );
}
