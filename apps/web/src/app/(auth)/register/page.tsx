import { RegisterForm } from '@/features/auth';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Create an account',
  description: 'Create a TrustLens account and start earning a verified seller Trust Score.',
};

export default function RegisterPage() {
  return (
    <>
      <h1 className="text-2xl font-bold">Create an account</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Already registered?{' '}
        <Link href="/login" className="font-medium text-primary underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>

      <RegisterForm className="mt-8" />
    </>
  );
}
