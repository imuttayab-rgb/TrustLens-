/** Next.js route/layout composition for (seller)/dashboard/verification/phone: page. */
import { PhoneVerification } from '@/features/verification';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = { title: 'Verify your phone' };

export default function PhoneVerificationPage() {
  return (
    <div className="mx-auto max-w-md">
      <Link href="/dashboard" className="text-sm text-muted-foreground hover:underline">
        ← Back to dashboard
      </Link>
      <h1 className="mt-2 text-2xl font-bold">Verify your phone</h1>
      <p className="mt-1 text-sm text-muted-foreground">Worth up to 15 points.</p>

      <div className="mt-8">
        <PhoneVerification />
      </div>
    </div>
  );
}
