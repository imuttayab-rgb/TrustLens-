import { SiteNav } from '@/features/marketing';
import Link from 'next/link';

/** The public marketing surface: full-strength ambient light and a footer. */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div data-surface="marketing" className="min-h-dvh bg-background text-foreground">
      <SiteNav />
      {children}
      <footer className="border-t border-border/70">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:px-8">
          <p>© {new Date().getFullYear()} TrustLens</p>
          <nav className="flex flex-wrap gap-5 sm:ml-auto">
            <Link href="/browse" className="transition-colors hover:text-foreground">
              Browse
            </Link>
            <Link href="/check" className="transition-colors hover:text-foreground">
              Check a seller
            </Link>
            <Link href="/help" className="transition-colors hover:text-foreground">
              Help
            </Link>
            <Link href="/terms" className="transition-colors hover:text-foreground">
              Terms
            </Link>
            <Link href="/privacy" className="transition-colors hover:text-foreground">
              Privacy
            </Link>
            <Link href="/docs/api" className="transition-colors hover:text-foreground">
              API docs
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
