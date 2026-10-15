/** Next.js route/layout composition for (seller): layout. */
import Link from 'next/link';
import { RequireSession } from '@/features/auth';
import { DeviceCheck } from '@/features/verification';
import { Ambient } from '@trustlens/ui';
import { SiteNav } from '@/features/marketing';
import { getTranslations } from 'next-intl/server';
import { DashboardNav } from './DashboardNav';

const NAV = [
  { href: '/browse', key: 'browse' },
  { href: '/dashboard', key: 'overview' },
  { href: '/dashboard/listings', key: 'selling' },
  { href: '/favourites', key: 'favorites' },
  { href: '/messages', key: 'messages' },
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

      <SiteNav />

      <main
        id="main-content"
        className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-10"
      >
        <RequireSession>
          <DashboardNav
            items={NAV.map((item) => ({
              href: item.href,
              label:
                item.key === 'overview'
                  ? 'My Profile'
                  : item.key === 'selling'
                    ? 'My Ads'
                    : t(item.key),
            }))}
          />
          <div className="mb-4 text-sm">
            <Link href="/dashboard/addresses" className="text-brand underline">
              Private details &amp; saved addresses
            </Link>
          </div>
          {children}
        </RequireSession>
      </main>

      {/* Runs once per session, renders nothing, and never blocks the page. */}
      <DeviceCheck />
    </div>
  );
}
