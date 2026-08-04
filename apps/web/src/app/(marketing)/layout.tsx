import { SiteNav } from '@/features/marketing';
import Link from 'next/link';

/**
 * The public surface.
 *
 * `data-surface="marketing"` switches this subtree to the dark token set. The
 * signed-in app keeps its own theme: a dashboard someone works in all day and
 * a landing page seen once have genuinely different needs, and forcing one
 * palette on both would serve neither.
 */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div data-surface="marketing" className="min-h-dvh bg-background text-foreground">
      <SiteNav />
      {children}
      <footer className="border-t border-border/70">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:px-8">
          <p>© {new Date().getFullYear()} TrustLens</p>
          <nav className="flex gap-5 sm:ml-auto">
            <Link href="/check" className="transition-colors hover:text-foreground">
              Check a seller
            </Link>
            <Link href="/login" className="transition-colors hover:text-foreground">
              Log in
            </Link>
            <Link href="/register" className="transition-colors hover:text-foreground">
              Get verified
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
