import { Facebook, Instagram, ShieldCheck, Twitter, Youtube } from 'lucide-react';
import { getTranslations } from 'next-intl/server';
import Link from 'next/link';

const LINK_CLASS =
  'rounded-sm transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

/**
 * Placeholder destinations - swap each for TrustLens' real profile once one
 * exists. Kept as `#` rather than omitted so the icon row's layout (and the
 * "add your real link here" spot for each platform) is already in place.
 */
const SOCIAL_LINKS = [
  { icon: Facebook, label: 'Facebook', href: '#' },
  { icon: Instagram, label: 'Instagram', href: '#' },
  { icon: Youtube, label: 'YouTube', href: '#' },
  { icon: Twitter, label: 'X (Twitter)', href: '#' },
] as const;

/**
 * Grouped by what a visitor is trying to do, not by when each page was
 * built. Legal pages sit in the bottom bar rather than their own column -
 * this product has no country selector or developer portal to fill a
 * "For Businesses" column the way a template one does, so it stays a
 * shorter, honest list of pages that actually exist.
 */
export async function SiteFooter() {
  const t = await getTranslations('SiteFooter');

  const columns = [
    {
      heading: t('marketplace'),
      links: [
        { href: '/browse', label: t('browse') },
        { href: '/check', label: t('checkSeller') },
        { href: '/register', label: t('getVerified') },
      ],
    },
    {
      heading: t('trustSafety'),
      links: [
        { href: '/safety', label: t('safety') },
        { href: '/community-guidelines', label: t('guidelines') },
        { href: '/report-issue', label: t('reportIssue') },
      ],
    },
    {
      heading: t('support'),
      links: [
        { href: '/help', label: t('help') },
        { href: '/contact', label: t('contact') },
      ],
    },
    {
      heading: t('forBusinesses'),
      links: [
        { href: '/docs/api', label: t('apiDocs') },
        { href: '/dashboard/verification/business', label: t('businessAccounts') },
      ],
    },
  ];

  const legalLinks = [
    { href: '/terms', label: t('terms') },
    { href: '/privacy', label: t('privacy') },
    { href: '/community-guidelines', label: t('guidelines') },
  ];

  return (
    <footer className="border-t border-border/70">
      <div className="mx-auto max-w-7xl px-5 py-10 sm:px-8">
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

            <div className="mt-4 flex items-center gap-2">
              {SOCIAL_LINKS.map((social) => {
                const Icon = social.icon;
                return (
                  <a
                    key={social.label}
                    href={social.href}
                    aria-label={social.label}
                    className="grid h-8 w-8 place-items-center rounded-full border border-border text-muted-foreground transition-colors hover:border-brand/40 hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                  </a>
                );
              })}
            </div>
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

        <div className="mt-10 flex flex-col gap-3 border-t border-border/60 pt-6 text-sm text-muted-foreground sm:flex-row sm:items-center">
          <p>{t('copyright', { year: new Date().getFullYear() })}</p>
          <nav aria-label={t('legal')} className="flex flex-wrap gap-4 sm:ml-auto">
            {legalLinks.map((link) => (
              <Link key={link.href} href={link.href} className={LINK_CLASS}>
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
    </footer>
  );
}
