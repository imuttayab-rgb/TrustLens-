/** Next.js route/layout composition for (marketing)/report-issue: page. */
import Link from 'next/link';

export const metadata = {
  title: 'Report an Issue · TrustLens',
  description: 'Report a listing, seller, or message that breaks TrustLens Community Guidelines.',
};

const REPORT_EMAIL = 'support@trustlens.dev';

function ReportCategory({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border/60 p-4">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{children}</p>
    </div>
  );
}

export default async function ReportIssuePage({
  searchParams,
}: {
  searchParams: Promise<{ seller?: string }>;
}) {
  const { seller } = await searchParams;
  const subject = encodeURIComponent('TrustLens report');
  const body = encodeURIComponent(
    [
      'What are you reporting? (a listing / a seller / a message / something else)',
      '',
      `Link or handle of the listing/seller, if you have one: ${seller ?? ''}`,
      '',
      'What happened?',
      '',
      '(If this is urgent - an active scam attempt, a threat, or a safety concern - say so in the first line.)',
    ].join('\n'),
  );

  return (
    <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8">
      <header>
        <p className="text-sm font-medium text-brand">Report an issue</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">
          Report a listing, seller, or message
        </h1>
        <p className="mt-3 text-muted-foreground">
          Reports are reviewed by TrustLens staff, not resolved automatically. You don&apos;t need
          to have lost anything, or be certain something is wrong, to report it - see{' '}
          <Link
            href="/community-guidelines"
            className="text-primary underline-offset-4 hover:underline"
          >
            Community Guidelines
          </Link>{' '}
          for what we act on.
        </p>
      </header>

      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        <ReportCategory title="A listing">
          Fake, misleading, prohibited, or describing something that doesn&apos;t match the photos.
        </ReportCategory>
        <ReportCategory title="A seller">
          Scam-pattern behavior, harassment, or requesting payment before you&apos;ve seen the item.
        </ReportCategory>
        <ReportCategory title="A message">
          Threatening, abusive, or requesting an OTP/password/verification code from you.
        </ReportCategory>
        <ReportCategory title="Something else">
          A safety concern, a suspected fake Trust Score, or anything not covered above.
        </ReportCategory>
      </div>

      <div className="mt-8 rounded-lg border border-border/70 bg-muted/30 p-5">
        <p className="font-semibold">How to report right now</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Email{' '}
          <a
            href={`mailto:${REPORT_EMAIL}?subject=${subject}&body=${body}`}
            className="text-primary underline-offset-4 hover:underline"
          >
            {REPORT_EMAIL}
          </a>{' '}
          with what you&apos;re reporting and a link or handle if you have one - the template above
          is pre-filled for you. Include &quot;urgent&quot; in the first line if it&apos;s an active
          scam attempt or a safety concern, so it gets looked at first.
        </p>
      </div>

      <p className="mt-6 text-sm text-muted-foreground">
        For general questions rather than a report, see{' '}
        <Link href="/contact" className="text-primary underline-offset-4 hover:underline">
          Contact
        </Link>{' '}
        or{' '}
        <Link href="/help" className="text-primary underline-offset-4 hover:underline">
          Help
        </Link>
        .
      </p>
    </main>
  );
}
