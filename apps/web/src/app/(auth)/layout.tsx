import { SiteNav } from '@/features/marketing';
import { Ambient } from '@trustlens/ui';

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

      <SiteNav />

      <main
        id="main-content"
        className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 pb-16"
      >
        {/* The form sits on glass, like every other panel in the product. */}
        <div className="rounded-2xl border border-border/70 bg-card/60 p-6 shadow-[0_0_0_1px_hsl(var(--brand)/0.05),0_24px_70px_-40px_hsl(var(--brand)/0.4)] backdrop-blur-xl sm:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
