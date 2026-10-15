/** Next.js route/layout composition for (auth-split)/login: page. */
import { LoginForm } from '@/features/auth';
import type { Metadata } from 'next';
import { Suspense } from 'react';
import { AuthTabs } from '../AuthTabs';

export const metadata: Metadata = { title: 'Sign in' };

export default function LoginPage() {
  return (
    <>
      <AuthTabs />
      <h1 className="mt-6 text-2xl font-bold">Welcome back</h1>
      <p className="mt-1 text-sm text-muted-foreground">Sign in to your TrustLens account.</p>

      {/* LoginForm reads ?next= via useSearchParams, which opts the route into
          client rendering unless it sits behind a Suspense boundary. */}
      <Suspense fallback={<div className="mt-8 h-64" aria-hidden="true" />}>
        <LoginForm className="mt-8" />
      </Suspense>
    </>
  );
}
