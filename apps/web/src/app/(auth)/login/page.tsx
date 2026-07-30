import { LoginForm } from '@/features/auth';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = { title: 'Sign in' };

export default function LoginPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-bold">Sign in</h1>
      <p className="text-muted-foreground mt-1 text-sm">
        New here?{' '}
        <Link href="/register" className="text-primary font-medium underline-offset-4 hover:underline">
          Create an account
        </Link>
      </p>
      <LoginForm className="mt-8" />
    </main>
  );
}
