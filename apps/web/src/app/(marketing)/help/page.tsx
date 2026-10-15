/** Next.js route/layout composition for (marketing)/help: page. */
import Link from 'next/link';

export const metadata = {
  title: 'Help · TrustLens',
  description: 'Answers to common questions about Trust Scores, verification, and listings.',
};

function Question({ q, children }: { q: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-border/60 py-6 first:border-t-0 first:pt-0">
      <h3 className="font-semibold">{q}</h3>
      <div className="mt-2 space-y-2 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </div>
  );
}

export default function HelpPage() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8">
      <header>
        <p className="text-sm font-medium text-brand">Help</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Frequently asked questions</h1>
        <p className="mt-3 text-muted-foreground">
          Can&apos;t find what you&apos;re looking for? Message a seller directly from their
          listing, or reach us at the address below.
        </p>
      </header>

      <div className="mt-8">
        <Question q="What is a Trust Score?">
          <p>
            A number from 0 to 100, built from identity, phone, email, device and listing checks a
            seller has completed. It is a summary of what has been verified, not a personal
            endorsement - always inspect goods before paying, and never send advance payment to
            someone you have not met in person.
          </p>
        </Question>

        <Question q="How is this different from OLX or Facebook Marketplace, which also send an OTP?">
          <p>
            An OTP only proves someone controls a phone number for a moment - it says nothing about
            whether the person behind the listing is who they claim to be. TrustLens additionally
            checks that a submitted CNIC looks genuine and that a live selfie matches the photo on
            it, and every listing is screened for scam-pattern language before it goes live. The
            score combines all of that, not just one signal.
          </p>
        </Question>

        <Question q="Is this a government or NADRA identity check?">
          <p>
            No. There is no public NADRA verification API available at this level, and TrustLens
            does not claim to be one. Identity verification here means document plausibility and
            face matching against the submitted CNIC - not a check against any government record.
          </p>
        </Question>

        <Question q="Why does a seller I trust have a low score?">
          <p>
            Usually because they have not completed verification yet, not because something was
            found wrong. A brand-new account with no checks completed is scored as unknown, not as
            risky - open their page to see exactly which checks are outstanding.
          </p>
        </Question>

        <Question q="I think my score is wrong. What can I do?">
          <p>
            Every reason behind your score is shown on your dashboard. If you believe one is wrong,
            you can appeal it - open{' '}
            <Link
              href="/dashboard/trust-score"
              className="text-primary underline-offset-4 hover:underline"
            >
              Trust Score
            </Link>{' '}
            from your dashboard and use the appeal option next to the signal in question.
          </p>
        </Question>

        <Question q="How do I contact a seller?">
          <p>
            Open a listing from{' '}
            <Link href="/browse" className="text-primary underline-offset-4 hover:underline">
              Browse
            </Link>{' '}
            and use the message button to start a conversation with the seller directly.
          </p>
        </Question>

        <Question q="How long is my CNIC photo kept?">
          <p>
            90 days after your verification is finally approved or rejected, then it is deleted. See
            the{' '}
            <Link href="/privacy" className="text-primary underline-offset-4 hover:underline">
              Privacy Policy
            </Link>{' '}
            for the full detail.
          </p>
        </Question>

        <Question q="Still stuck?">
          <p>
            Email{' '}
            <a
              href="mailto:support@trustlens.dev"
              className="text-primary underline-offset-4 hover:underline"
            >
              support@trustlens.dev
            </a>{' '}
            with your account email and a description of the problem.
          </p>
        </Question>
      </div>
    </main>
  );
}
