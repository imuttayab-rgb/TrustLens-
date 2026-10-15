/** Next.js route/layout composition for (auth)/forgot-password: page. */
import { ForgotPasswordForm } from '@/features/auth';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = { title: 'Reset your password' };

export default function ForgotPasswordPage() {
  return (
    <>
      <h1 className="text-2xl font-bold">Reset your password</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Remembered it?{' '}
        <Link href="/login" className="font-medium text-primary underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>

      <ForgotPasswordForm className="mt-8" />
    </>
  );
}
