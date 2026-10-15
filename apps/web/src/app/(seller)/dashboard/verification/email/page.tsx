/** Next.js route/layout composition for (seller)/dashboard/verification/email: page. */
'use client';

import { EmailVerification } from '@/features/verification';
import { useVerificationStatus } from '@/features/seller';
import { useSession } from '@/lib/auth/use-session';
import { Spinner } from '@trustlens/ui';
import Link from 'next/link';

export default function EmailVerificationPage() {
  // The address lives on /me; whether it is confirmed lives on the
  // verification status endpoint, the single source of truth for check state.
  const { data: user, isPending } = useSession();
  const { data: status } = useVerificationStatus();

  return (
    <div className="mx-auto max-w-md">
      <Link href="/dashboard" className="text-sm text-muted-foreground hover:underline">
        ← Back to dashboard
      </Link>
      <h1 className="mt-2 text-2xl font-bold">Verify your email</h1>
      <p className="mt-1 text-sm text-muted-foreground">Worth up to 10 points.</p>

      <div className="mt-8">
        {isPending ? (
          <Spinner label="Loading your email address" />
        ) : (
          <EmailVerification email={user?.email ?? ''} verified={status?.email === 'VERIFIED'} />
        )}
      </div>
    </div>
  );
}
