import { VerifyEmailPanel } from '@/features/auth';
import type { Metadata } from 'next';
import { Suspense } from 'react';

export const metadata: Metadata = { title: 'Confirm your email', robots: { index: false } };

export default function VerifyEmailPage() {
  return (
    <>
      <h1 className="text-2xl font-bold">Confirm your email</h1>
      <div className="mt-8">
        <Suspense fallback={<div className="h-24" aria-hidden="true" />}>
          <VerifyEmailPanel />
        </Suspense>
      </div>
    </>
  );
}
