/** Reusable UI rendering and interaction component: RequireSession. */
'use client';

import { useMyProfile } from '@/features/profile';
import { Alert, Button } from '@trustlens/ui';
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
  const { data: user, isPending, isFetching } = useSession();
  const checking = isPending || (!user && isFetching);

  useEffect(() => {
    if (!checking && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [checking, user, pathname, router]);

  if (checking) {
    return (
      <div className="flex min-h-[50dvh] items-center justify-center">
        <Spinner label="Loading your account" />
      </div>
    );
  }

  // The redirect above is already in flight; rendering nothing avoids a
  // flash of the signed-out state.
  if (!user) return null;

  return <ProfileBootstrap>{children}</ProfileBootstrap>;
}

function ProfileBootstrap({ children }: { children: React.ReactNode }) {
  const { data, isPending, error, refetch } = useMyProfile();
  if (isPending)
    return (
      <div className="py-16">
        <Spinner label="Preparing your profile" />
      </div>
    );
  if (error || !data?.initialized)
    return (
      <Alert tone="error" title="Profile setup could not finish">
        {error?.message}
        <Button variant="outline" onClick={() => void refetch()}>
          Retry
        </Button>
      </Alert>
    );
  return <>{children}</>;
}
