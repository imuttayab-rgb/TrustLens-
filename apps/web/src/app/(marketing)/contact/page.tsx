/** Next.js route/layout composition for (marketing)/contact: page. */
import Link from 'next/link';

export const metadata = {
  title: 'Contact · TrustLens',
  description: 'How to reach TrustLens for support, a report, or a press/partnership inquiry.',
};

const SUPPORT_EMAIL = 'support@trustlens.dev';

function ContactRow({
  title,
  description,
  href,
  linkLabel,
}: {
  title: string;
  description: string;
  href: string;
  linkLabel: string;
}) {
  return (
    <div className="flex flex-col gap-1 border-t border-border/60 py-6 first:border-t-0 first:pt-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6">
      <div>
        <p className="font-semibold">{title}</p>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      <Link
        href={href}
        className="shrink-0 text-sm text-primary underline-offset-4 hover:underline"
      >
        {linkLabel}
      </Link>
    </div>
  );
}

export default function ContactPage() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8">
      <header>
        <p className="text-sm font-medium text-brand">Contact</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Get in touch</h1>
        <p className="mt-3 text-muted-foreground">
          Pick the option below that matches what you need - it gets you a faster answer than one
          general inbox.
        </p>
      </header>

      <div className="mt-8">
        <ContactRow
          title="Report a listing, seller, or message"
          description="Something breaks Community Guidelines, or feels like a scam."
          href="/report-issue"
          linkLabel="Report an issue →"
        />
        <ContactRow
          title="A question about how TrustLens works"
          description="How a Trust Score is calculated, verification, appeals, and general how-to."
          href="/help"
          linkLabel="Help →"
        />
        <ContactRow
          title="A safety concern before meeting a buyer or seller"
          description="What to do, and what a Trust Score does and does not promise."
          href="/safety"
          linkLabel="Safety →"
        />
        <ContactRow
          title="Everything else"
          description="Press, partnerships, account issues not covered above, or general feedback."
          href={`mailto:${SUPPORT_EMAIL}`}
          linkLabel={SUPPORT_EMAIL}
        />
      </div>
    </main>
  );
}
