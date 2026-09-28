import { RequireSession } from '@/features/auth';
import { DeviceCheck } from '@/features/verification';
import { Ambient } from '@trustlens/ui';
import { ShieldCheck } from 'lucide-react';
import { getTranslations } from 'next-intl/server';
import Link from 'next/link';
import { DashboardNav } from './DashboardNav';

const NAV = [
  { href: '/browse', key: 'browse' },
  { href: '/dashboard', key: 'overview' },
  { href: '/dashboard/listings', key: 'selling' },
  { href: '/dashboard/favorites', key: 'favorites' },
  { href: '/dashboard/messages', key: 'messages' },
  { href: '/dashboard/trust-score', key: 'score' },
  { href: '/dashboard/reports', key: 'myReports' },
  { href: '/dashboard/settings', key: 'settings' },
] as const;

/**
 * Shell for every signed-in seller screen.
 *
 * The auth gate lives here rather than on each page: one missed check on one
 * route is all it takes to leak a dashboard, and this layout wraps them all.
 */
export default async function SellerLayout({ children }: { children: React.ReactNode }) {
  const t = await getTranslations('DashboardNav');
  return (
    <div className="relative flex min-h-dvh flex-col overflow-hidden">
      {/* Subtle, not full: this is a screen people work in, and full-strength
          light would compete with the score gauge for attention. */}
      <Ambient />

      <header className="sticky top-0 z-20 border-b border-border/70 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link
            href="/dashboard"
            className="group flex items-center gap-2.5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-brand to-brand-2 transition-transform duration-300 group-hover:scale-105">
              <ShieldCheck
                className="h-3.5 w-3.5 text-[hsl(var(--background))]"
                strokeWidth={2.5}
                aria-hidden="true"
              />
            </span>
            <span className="text-sm font-bold tracking-tight">TrustLens</span>
          </Link>

          <DashboardNav items={NAV.map((item) => ({ href: item.href, label: t(item.key) }))} />
        </div>
      </header>

      <main
        id="main-content"
        className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 sm:px-6 sm:py-10"
      >
        <RequireSession>{children}</RequireSession>
      </main>

      {/* Runs once per session, renders nothing, and never blocks the page. */}
      <DeviceCheck />
    </div>
  );
}
