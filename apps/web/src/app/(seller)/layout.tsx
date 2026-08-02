import { RequireSession } from '@/features/auth';
import { DeviceCheck } from '@/features/verification';
import Link from 'next/link';

/**
 * Shell for every signed-in seller screen.
 *
 * The auth gate lives here rather than on each page: one missed check on one
 * route is all it takes to leak a dashboard, and this layout wraps them all.
 */
export default function SellerLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link href="/dashboard" className="font-bold tracking-tight">
            TrustLens
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <Link href="/dashboard" className="rounded-md px-3 py-2 hover:bg-muted">
              Overview
            </Link>
            <Link href="/dashboard/trust-score" className="rounded-md px-3 py-2 hover:bg-muted">
              Score
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 sm:px-6 sm:py-10">
        <RequireSession>{children}</RequireSession>
      </main>

      {/* Runs once per session, renders nothing, and never blocks the page. */}
      <DeviceCheck />
    </div>
  );
}
