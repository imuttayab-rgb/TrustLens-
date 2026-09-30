import { ThemeToggle } from '@trustlens/ui';
import { HelpCircle, ShieldCheck } from 'lucide-react';
import Link from 'next/link';
import { AuthMarketingPanel } from './AuthMarketingPanel';

/**
 * Shell for login/register specifically - the two-column marketing layout
 * only makes sense with the Login/Create account tabs, so this is its own
 * route group rather than a variant of the plain centred layout the other
 * signed-out screens (forgot/reset password, verify email) use.
 */
export default function AuthSplitLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <Link
          href="/"
          className="group inline-flex items-center gap-2.5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand to-brand-2 transition-transform duration-300 group-hover:scale-105">
            <ShieldCheck
              className="h-4 w-4 text-[hsl(var(--background))]"
              strokeWidth={2.5}
              aria-hidden="true"
            />
          </span>
          <span className="text-lg font-bold tracking-tight">TrustLens</span>
        </Link>

        <nav className="flex items-center gap-5 text-sm text-muted-foreground">
          <Link href="/" className="hidden items-center gap-1.5 hover:text-foreground sm:flex">
            ← Back to Marketplace
          </Link>
          <Link href="/help" className="flex items-center gap-1.5 hover:text-foreground">
            <HelpCircle className="h-4 w-4" aria-hidden="true" />
            Help
          </Link>
          <Link href="/safety" className="flex items-center gap-1.5 hover:text-foreground">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Safety
          </Link>
          <ThemeToggle />
        </nav>
      </header>

      <div className="grid flex-1 lg:grid-cols-2">
        <AuthMarketingPanel />

        <main id="main-content" className="flex items-center justify-center px-6 py-10 sm:py-16">
          <div className="w-full max-w-md">{children}</div>
        </main>
      </div>
    </div>
  );
}
