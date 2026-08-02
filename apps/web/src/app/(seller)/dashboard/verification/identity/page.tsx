import { IdentityVerification } from '@/features/verification';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = { title: 'Verify your identity' };

export default function IdentityVerificationPage() {
  return (
    <>
      <Link href="/dashboard" className="text-sm text-muted-foreground hover:underline">
        ← Back to dashboard
      </Link>
      <h1 className="mt-2 text-2xl font-bold">Verify your identity</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Worth up to 30 points — the largest single contribution to your Trust Score.
      </p>

      <div className="mt-8">
        <IdentityVerification />
      </div>
    </>
  );
}
