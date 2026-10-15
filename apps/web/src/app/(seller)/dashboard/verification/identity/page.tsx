/** Next.js route/layout composition for (seller)/dashboard/verification/identity: page. */
import { IdentityVerification, LIVE_WIZARD_ENABLED } from '@/features/verification';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = { title: 'Verify your identity' };

export default function IdentityVerificationPage() {
  return (
    <>
      <Link href="/dashboard" className="text-sm text-muted-foreground hover:underline">
        ← Back to dashboard
      </Link>
      {/* The live step-by-step wizard renders its own title, step counter
          and stepper, so this heading is only used by the classic form. */}
      {!LIVE_WIZARD_ENABLED && (
        <>
          <h1 className="mt-2 text-2xl font-bold">Verify your identity</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Worth up to 30 points — the largest single contribution to your Trust Score.
          </p>
        </>
      )}

      <div className={LIVE_WIZARD_ENABLED ? 'mt-4' : 'mt-8'}>
        <IdentityVerification />
      </div>
    </>
  );
}
