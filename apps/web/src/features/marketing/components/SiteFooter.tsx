import { ShieldCheck } from 'lucide-react';
import { getTranslations } from 'next-intl/server';
import Link from 'next/link';

const LINK_CLASS =
  'rounded-sm transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

/**
 * Grouped by what a visitor is trying to do, not by when each page was
 * built. Legal and trust-and-safety pages get their own columns because
 * they are the pages a cautious buyer (this product's whole audience)
 * actually goes looking for.
 */
export async function SiteFooter() {
  const t = await getTranslations('SiteFooter');

  const columns = [
    {
      heading: t('product'),
      links: [
        { href: '/browse', label: t('browse') },
        { href: '/check', label: t('checkSeller') },
        { href: '/register', label: t('getVerified') },
        { href: '/docs/api', label: t('apiDocs') },
      ],
    },
    {
      heading: t('support'),
      links: [
        { href: '/help', label: t('help') },
        { href: '/contact', label: t('contact') },
        { href: '/report-issue', label: t('reportIssue') },
      ],
    },
    {
      heading: t('trustSafety'),
      links: [
        { href: '/safety', label: t('safety') },
        { href: '/community-guidelines', label: t('guidelines') },
      ],
    },
    {
      heading: t('legal'),
      links: [
        { href: '/terms', label: t('terms') },
        { href: '/privacy', label: t('privacy') },
      ],
    },
  ];

  return (
    <footer className="border-t border-border/70">
      <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-[1.4fr_repeat(4,1fr)]">
          <div className="max-w-xs">
            <Link
              href="/"
              className="inline-flex items-center gap-2.5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand to-brand-2">
                <ShieldCheck
                  className="h-4 w-4 text-[hsl(var(--background))]"
                  strokeWidth={2.5}
                  aria-hidden="true"
                />
              </span>
              <span className="text-sm font-bold tracking-tight">TrustLens</span>
            </Link>
            <p className="mt-3 text-sm text-muted-foreground">{t('blurb')}</p>
          </div>

          {columns.map((column) => (
            <nav key={column.heading} aria-label={column.heading}>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-foreground">
                {column.heading}
              </h2>
              <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className={LINK_CLASS}>
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-10 border-t border-border/60 pt-6 text-sm text-muted-foreground">
          <p>{t('copyright', { year: new Date().getFullYear() })}</p>
        </div>
      </div>
    </footer>
  );
}
