import { SiteFooter, SiteNav } from '@/features/marketing';

/** The public marketing surface: full-strength ambient light and a footer. */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div data-surface="marketing" className="min-h-dvh bg-background text-foreground">
      <SiteNav />
      <main id="main-content">{children}</main>
      <SiteFooter />
    </div>
  );
}
