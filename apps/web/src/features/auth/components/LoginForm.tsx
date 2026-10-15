/** Reusable UI rendering and interaction component: LoginForm. */
'use client';

import { api } from '@/lib/api/client';
import { setAccessToken } from '@/lib/auth/session';
import { useApiForm } from '@/lib/forms/use-api-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input, PasswordInput } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { loginSchema, type LoginInput } from '@trustlens/validation';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { useState } from 'react';
import { GoogleAuthButton } from './GoogleAuthButton';
import { safeNext } from '@/lib/auth/safe-next';

export function LoginForm({ className }: { className?: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const next = safeNext(params.get('next'));
  const googleError = params.get('error') === 'google';
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState('');
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [mfaBusy, setMfaBusy] = useState(false);
  const googleMfa = params.get('mfa') === 'google';
  function finishSignIn(token: string) {
    setAccessToken(token);
    queryClient.clear();
    router.push(next);
  }
  async function finishMfa() {
    setMfaBusy(true);
    setMfaError(null);
    try {
      const result = googleMfa
        ? await api.POST('/api/v1/auth/google/mfa/verify', { body: { code: mfaCode } })
        : await api.POST('/api/v1/auth/mfa/verify', {
            body: { mfaToken: mfaToken!, code: mfaCode },
          });
      if (result.error) throw toApiError(result.error);
      const token = (result.data as { data: { accessToken?: string } }).data.accessToken;
      if (!token) throw new Error('Sign-in did not complete. Try again.');
      finishSignIn(token);
    } catch (error) {
      setMfaError(error instanceof Error ? error.message : 'Could not verify this code.');
    } finally {
      setMfaBusy(false);
    }
  }

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>({ resolver: zodResolver(loginSchema) });

  const { submit, formError } = useApiForm<LoginInput>(setError);

  const onSubmit = handleSubmit(async (values) => {
    let token: string | undefined;
    const ok = await submit(async () => {
      const result = await api.POST('/api/v1/auth/login', { body: values });
      if (result.error) throw toApiError(result.error);
      const data = (
        result.data as { data: { accessToken?: string; mfaRequired?: boolean; mfaToken?: string } }
      ).data;
      if (data.mfaRequired && data.mfaToken) {
        setMfaToken(data.mfaToken);
        return;
      }
      if (!data.accessToken) throw new Error('Sign-in did not complete.');
      token = data.accessToken;
    });
    if (ok && token) finishSignIn(token);
  });

  if (mfaToken || googleMfa)
    return (
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          void finishMfa();
        }}
      >
        <h2 className="text-lg font-semibold">Verify your sign-in</h2>
        <p className="text-sm text-muted-foreground">
          Enter your authenticator code or one unused recovery code.
        </p>
        <Field htmlFor="mfa-code" label="Verification code">
          <Input
            id="mfa-code"
            autoComplete="one-time-code"
            value={mfaCode}
            onChange={(e) => setMfaCode(e.target.value)}
            maxLength={40}
            required
          />
        </Field>
        {mfaError && <Alert tone="error">{mfaError}</Alert>}
        <Button type="submit" disabled={mfaBusy || !mfaCode.trim()}>
          {mfaBusy ? 'Verifying…' : 'Verify and sign in'}
        </Button>
        <Link
          href="/login"
          onClick={() => {
            setMfaToken(null);
            setMfaCode('');
          }}
          className="ms-3 text-sm underline"
        >
          Start again
        </Link>
      </form>
    );

  return (
    <form
      onSubmit={(event) => void onSubmit(event)}
      className={cn('space-y-4', className)}
      noValidate
    >
      {googleError && (
        <Alert tone="error" className="animate-fade-in">
          Could not sign in with Google. Try again, or use your password.
        </Alert>
      )}

      <Field htmlFor="email" label="Email address" error={errors.email?.message}>
        <Input
          {...fieldAria('email', errors.email?.message)}
          type="email"
          inputMode="email"
          autoComplete="email"
          autoCapitalize="none"
          placeholder="Enter your email address"
          {...register('email')}
        />
      </Field>

      <Field htmlFor="password" label="Password" error={errors.password?.message}>
        <PasswordInput
          {...fieldAria('password', errors.password?.message)}
          autoComplete="current-password"
          placeholder="Enter your password"
          {...register('password')}
        />
      </Field>

      <div className="flex justify-end">
        <Link
          href="/forgot-password"
          className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          Forgot your password?
        </Link>
      </div>

      {formError && (
        <Alert tone="error" requestId={formError.requestId} className="animate-fade-in">
          {formError.message}
        </Alert>
      )}

      <Button
        type="submit"
        size="lg"
        className="w-full transition-transform duration-150 hover:scale-[1.01] active:scale-[0.99]"
        disabled={isSubmitting}
      >
        {isSubmitting ? 'Signing in…' : 'Sign in'}
      </Button>

      <div className="relative py-1 text-center text-xs text-muted-foreground">
        <span className="relative z-10 bg-background px-2">or</span>
        <div className="absolute inset-x-0 top-1/2 border-t border-border" />
      </div>

      <GoogleAuthButton next={next} />
      <p className="text-center text-xs text-muted-foreground">
        Signing in with Google for the first time creates an account, and agrees to the{' '}
        <Link href="/terms" className="underline-offset-4 hover:underline">
          terms
        </Link>{' '}
        and{' '}
        <Link href="/privacy" className="underline-offset-4 hover:underline">
          privacy policy
        </Link>
        .
      </p>
    </form>
  );
}
