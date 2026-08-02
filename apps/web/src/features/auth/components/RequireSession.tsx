'use client';

import { useSession } from '@/lib/auth/use-session';
import { Spinner } from '@trustlens/ui';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';

/**
 * Client-side auth guard for the seller area.
 *
 * See `useSession` for why this cannot be done on the server. Redirects carry
 * `?next=`, so signing in returns the seller to the page they asked for
 * instead of dropping them on a generic dashboard.
 */
export function RequireSession({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: user, isPending } = useSession();

  useEffect(() => {
    if (!isPending && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [isPending, user, pathname, router]);

  if (isPending) {
    return (
      <div className="flex min-h-[50dvh] items-center justify-center">
        <Spinner label="Loading your account" />
      </div>
    );
  }

  // The redirect above is already in flight; rendering nothing avoids a
  // flash of the signed-out state.
  if (!user) return null;

  return <>{children}</>;
}
