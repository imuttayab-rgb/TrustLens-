'use client';

import { STAFF_ROLES, useSession } from '@/lib/auth/use-session';
import { Alert, Spinner } from '@trustlens/ui';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';

/**
 * Gate for the whole admin app.
 *
 * Two distinct failures, kept distinct: not signed in sends you to the login
 * page, whereas signed in without a staff role is refused outright. Silently
 * redirecting a legitimate seller to a login form would tell them their
 * password was wrong, which it was not.
 *
 * This is convenience, not security - the API enforces the same permissions
 * per route, and it is the only enforcement that counts.
 */
export function RequireStaff({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: user, isPending, isFetching } = useSession();
  const checking = isPending || (!user && isFetching);

  const isStaff = Boolean(user?.roles.some((r) => (STAFF_ROLES as readonly string[]).includes(r)));

  useEffect(() => {
    if (!checking && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [checking, user, pathname, router]);

  if (checking) {
    return (
      <div className="flex min-h-[60dvh] items-center justify-center">
        <Spinner label="Checking your access" />
      </div>
    );
  }

  if (!user) return null;

  if (!isStaff) {
    return (
      <div className="mx-auto max-w-md p-8">
        <Alert tone="error" title="This account cannot open the admin panel">
          You are signed in as {user.email}, which has no reviewer or admin role. If that is wrong,
          ask an administrator to grant it.
        </Alert>
      </div>
    );
  }

  return <>{children}</>;
}
