import { SiteNav } from '@/features/marketing';
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
      <SiteNav />

      <div className="grid flex-1 lg:grid-cols-2">
        <AuthMarketingPanel />

        <main id="main-content" className="flex items-center justify-center px-6 py-10 sm:py-16">
          <div className="w-full max-w-md">{children}</div>
        </main>
      </div>
    </div>
  );
}
