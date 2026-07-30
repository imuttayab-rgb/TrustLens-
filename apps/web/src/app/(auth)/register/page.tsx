import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = { title: 'Create an account' };

export default function RegisterPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-bold">Create an account</h1>
      <p className="text-muted-foreground mt-1 text-sm">
        Already registered?{' '}
        <Link href="/login" className="text-primary font-medium underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>
      <p className="text-muted-foreground mt-8 text-sm">
        Registration form uses the shared <code>registerSchema</code> from{' '}
        <code>@trustlens/validation</code>, mirroring the backend rules.
      </p>
    </main>
  );
}
