import { LoginForm } from '@/features/auth';
import type { Metadata } from 'next';
import Link from 'next/link';
import { Suspense } from 'react';

export const metadata: Metadata = { title: 'Sign in' };

export default function LoginPage() {
  return (
    <>
      <h1 className="text-2xl font-bold">Sign in</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        New here?{' '}
        <Link
          href="/register"
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          Create an account
        </Link>
      </p>

      {/* LoginForm reads ?next= via useSearchParams, which opts the route into
          client rendering unless it sits behind a Suspense boundary. */}
      <Suspense fallback={<div className="mt-8 h-64" aria-hidden="true" />}>
        <LoginForm className="mt-8" />
      </Suspense>
    </>
  );
}
