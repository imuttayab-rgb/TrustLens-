import '@/styles/globals.css';

import { Providers } from '@/providers';
import { ADMIN_ROUTES } from '@trustlens/constants';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Link from 'next/link';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' });

export const metadata: Metadata = {
  title: { default: 'TrustLens Admin', template: '%s · TrustLens Admin' },
  // The admin panel must never be indexed. It is a separate deployment
  // precisely so it can be locked down independently of the public site.
  robots: { index: false, follow: false, nocache: true },
};

const NAV = [
  { href: ADMIN_ROUTES.overview, label: 'Overview' },
  { href: ADMIN_ROUTES.reviews, label: 'Review queue' },
  { href: ADMIN_ROUTES.sellers, label: 'Sellers' },
  { href: ADMIN_ROUTES.appeals, label: 'Appeals' },
  { href: ADMIN_ROUTES.scoring, label: 'Scoring models' },
  { href: ADMIN_ROUTES.apiClients, label: 'API clients' },
  { href: ADMIN_ROUTES.auditLogs, label: 'Audit log' },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-dvh">
        <Providers>
          <div className="flex min-h-dvh">
            <aside className="border-border bg-muted/30 w-60 shrink-0 border-r p-4">
              <p className="px-2 text-sm font-bold tracking-tight">TrustLens Admin</p>
              <nav aria-label="Admin" className="mt-6 space-y-1">
                {NAV.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="hover:bg-muted focus-visible:ring-ring block rounded-md px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2"
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
            </aside>
            <div className="min-w-0 flex-1">{children}</div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
