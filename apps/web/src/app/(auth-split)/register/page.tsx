/** Next.js route/layout composition for (auth-split)/register: page. */
import { RegisterForm } from '@/features/auth';
import type { Metadata } from 'next';
import { AuthTabs } from '../AuthTabs';

export const metadata: Metadata = {
  title: 'Create an account',
  description: 'Create a TrustLens account and start earning a verified seller Trust Score.',
};

export default function RegisterPage() {
  return (
    <>
      <AuthTabs />
      <h1 className="mt-6 text-2xl font-bold">Create your account</h1>
      <p className="mt-1 text-sm text-muted-foreground">Free to join. Verify to start selling.</p>

      <RegisterForm className="mt-8" />
    </>
  );
}
