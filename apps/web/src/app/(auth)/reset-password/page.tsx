/** Next.js route/layout composition for (auth)/reset-password: page. */
import { ResetPasswordForm } from '@/features/auth';
import type { Metadata } from 'next';
import { Suspense } from 'react';

export const metadata: Metadata = { title: 'Choose a new password', robots: { index: false } };

export default function ResetPasswordPage() {
  return (
    <>
      <h1 className="text-2xl font-bold">Choose a new password</h1>
      <Suspense fallback={<div className="mt-8 h-56" aria-hidden="true" />}>
        <ResetPasswordForm className="mt-8" />
      </Suspense>
    </>
  );
}
