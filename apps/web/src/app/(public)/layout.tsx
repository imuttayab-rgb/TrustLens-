import { SiteFooter, SiteNav } from '@/features/marketing';
import { Ambient } from '@trustlens/ui';

/**
 * Buyer-facing lookup pages.
 *
 * Shares the marketing nav deliberately: someone arriving from a seller's
 * badge link should land somewhere recognisably the same product, not on a
 * bare page with no way back.
 */
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-dvh flex-col overflow-hidden">
      <Ambient />
      <SiteNav />
      <main id="main-content" className="flex-1">
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}
