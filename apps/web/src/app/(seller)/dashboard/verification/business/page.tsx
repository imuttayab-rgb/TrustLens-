import { BusinessVerification } from '@/features/verification';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = { title: 'Verify your business' };

export default function BusinessVerificationPage() {
  return (
    <div className="mx-auto max-w-md">
      <Link href="/dashboard" className="text-sm text-muted-foreground hover:underline">
        ← Back to dashboard
      </Link>
      <h1 className="mt-2 text-2xl font-bold">Verify your business</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Shows a &quot;Verified business&quot; badge on your storefront once a staff reviewer
        approves it.
      </p>

      <div className="mt-8">
        <BusinessVerification />
      </div>
    </div>
  );
}
