import { Ambient, ThemeToggle } from '@trustlens/ui';
import { ShieldCheck } from 'lucide-react';
import Link from 'next/link';

/**
 * Shell for every signed-out screen.
 *
 * `min-h-dvh` rather than `min-h-screen`: on mobile Safari `100vh` counts the
 * area behind the browser chrome, so a centred form sits visibly too low and
 * the submit button can fall under the toolbar.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-dvh flex-col overflow-hidden">
      <Ambient intensity="full" />

      <header className="flex items-center justify-between px-6 py-5">
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
          <span className="text-sm font-bold tracking-tight">TrustLens</span>
        </Link>
        <ThemeToggle />
      </header>

      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 pb-16">
        {/* The form sits on glass, like every other panel in the product. */}
        <div className="rounded-2xl border border-border/70 bg-card/60 p-6 shadow-[0_0_0_1px_hsl(var(--brand)/0.05),0_24px_70px_-40px_hsl(var(--brand)/0.4)] backdrop-blur-xl sm:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
