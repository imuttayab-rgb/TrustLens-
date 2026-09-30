'use client';

import { api } from '@/lib/api/client';
import { setAccessToken } from '@/lib/auth/session';
import { useApiForm } from '@/lib/forms/use-api-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input, PasswordInput } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { registerSchema, type RegisterInput } from '@trustlens/validation';
import { Lock, Mail, ScanFace, ShoppingBag, Smartphone, Store } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { GoogleAuthButton } from './GoogleAuthButton';

const ONBOARDING_STEPS = [
  { icon: Mail, label: 'Email verified' },
  { icon: Smartphone, label: 'Phone verified' },
  { icon: ScanFace, label: 'Live ID check' },
] as const;

export function RegisterForm({ className }: { className?: string }) {
  const router = useRouter();
  const [done, setDone] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<RegisterInput>({
    resolver: zodResolver(registerSchema),
    defaultValues: { asSeller: true, acceptedTerms: false as unknown as true },
  });

  const asSeller = watch('asSeller');

  const { submit, formError } = useApiForm<RegisterInput>(setError);

  const onSubmit = handleSubmit(async (values) => {
    const ok = await submit(async () => {
      const result = await api.POST('/api/v1/auth/register', {
        // confirmPassword is a client-side cross-check; the API rejects
        // unknown fields, so it must not be sent.
        body: {
          email: values.email,
          password: values.password,
          fullName: values.fullName,
          asSeller: values.asSeller,
          acceptedTerms: values.acceptedTerms,
        },
      });
      if (result.error) throw toApiError(result.error);

      // Registration may or may not return a session depending on whether
      // email confirmation is required. Only treat it as signed in if a
      // token actually came back.
      const token = (result.data as { data?: { accessToken?: string } })?.data?.accessToken;
      if (token) setAccessToken(token);
    });

    if (ok) {
      setDone(values.email);
      router.refresh();
    }
  });

  if (done) {
    return (
      <div className={cn('animate-fade-up space-y-4', className)}>
        <Alert tone="success" title="Check your email">
          We sent a confirmation link to <strong>{done}</strong>. Open it to activate your account.
        </Alert>
        <p className="text-sm text-muted-foreground">
          Nothing arrived? Check your spam folder, or{' '}
          <Link
            href="/login"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            sign in
          </Link>{' '}
          to resend it.
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={(event) => void onSubmit(event)}
      className={cn('space-y-4', className)}
      noValidate
    >
      <Field htmlFor="fullName" label="Full name" required error={errors.fullName?.message}>
        <Input
          {...fieldAria('fullName', errors.fullName?.message)}
          autoComplete="name"
          autoCapitalize="words"
          placeholder="Enter your full name"
          {...register('fullName')}
        />
      </Field>

      <Field
        htmlFor="email"
        label="Email address"
        required
        error={errors.email?.message}
        hint="We send your verification link here."
      >
        <Input
          {...fieldAria('email', errors.email?.message, 'hint')}
          type="email"
          inputMode="email"
          autoComplete="email"
          autoCapitalize="none"
          placeholder="Enter your email address"
          {...register('email')}
        />
      </Field>

      <Field
        htmlFor="password"
        label="Password"
        required
        error={errors.password?.message}
        hint="At least 12 characters."
      >
        <PasswordInput
          {...fieldAria('password', errors.password?.message, 'hint')}
          autoComplete="new-password"
          placeholder="Create a strong password"
          {...register('password')}
        />
      </Field>

      <Field
        htmlFor="confirmPassword"
        label="Confirm password"
        required
        error={errors.confirmPassword?.message}
      >
        <PasswordInput
          {...fieldAria('confirmPassword', errors.confirmPassword?.message)}
          autoComplete="new-password"
          placeholder="Confirm your password"
          {...register('confirmPassword')}
        />
      </Field>

      <div className="space-y-2">
        <p className="text-sm font-medium">I want to:</p>
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setValue('asSeller', false)}
            aria-pressed={!asSeller}
            className={cn(
              'flex flex-col items-start gap-2 rounded-lg border p-3 text-left transition-all duration-150 hover:scale-[1.02] active:scale-[0.98]',
              !asSeller ? 'border-brand bg-brand/5 shadow-sm' : 'border-input hover:bg-muted',
            )}
          >
            <ShoppingBag className="h-5 w-5 text-brand" aria-hidden="true" />
            <span className="text-sm font-semibold">Buy only</span>
            <span className="text-xs text-muted-foreground">
              Browse and buy items from trusted sellers.
            </span>
          </button>
          <button
            type="button"
            onClick={() => setValue('asSeller', true)}
            aria-pressed={asSeller}
            className={cn(
              'flex flex-col items-start gap-2 rounded-lg border p-3 text-left transition-all duration-150 hover:scale-[1.02] active:scale-[0.98]',
              asSeller ? 'border-brand bg-brand/5 shadow-sm' : 'border-input hover:bg-muted',
            )}
          >
            <Store className="h-5 w-5 text-brand" aria-hidden="true" />
            <span className="text-sm font-semibold">Buy &amp; Sell</span>
            <span className="text-xs text-muted-foreground">
              Buy items and earn a Trust Score selling your own.
            </span>
          </button>
        </div>
      </div>

      <div className="space-y-3 pt-1">
        <label className="flex cursor-pointer items-start gap-3 text-sm">
          <input
            type="checkbox"
            aria-invalid={errors.acceptedTerms ? true : undefined}
            aria-describedby={errors.acceptedTerms ? 'terms-error' : undefined}
            className="mt-0.5 h-4 w-4 shrink-0 rounded border-input text-primary focus-visible:ring-2 focus-visible:ring-ring"
            {...register('acceptedTerms')}
          />
          <span>
            I accept the{' '}
            <Link href="/terms" className="text-primary underline-offset-4 hover:underline">
              terms
            </Link>{' '}
            and{' '}
            <Link href="/privacy" className="text-primary underline-offset-4 hover:underline">
              privacy policy
            </Link>
          </span>
        </label>
        {errors.acceptedTerms && (
          <p id="terms-error" role="alert" className="animate-fade-in text-sm text-destructive">
            {errors.acceptedTerms.message}
          </p>
        )}
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
        {isSubmitting ? 'Creating your account…' : 'Create account'}
      </Button>

      <div className="relative py-1 text-center text-xs text-muted-foreground">
        <span className="relative z-10 bg-background px-2">or</span>
        <div className="absolute inset-x-0 top-1/2 border-t border-border" />
      </div>

      <GoogleAuthButton label="Continue with Google" />
      <p className="text-center text-xs text-muted-foreground">
        Creates an account instantly, verified - no confirmation email needed. By continuing you
        agree to the{' '}
        <Link href="/terms" className="underline-offset-4 hover:underline">
          terms
        </Link>{' '}
        and{' '}
        <Link href="/privacy" className="underline-offset-4 hover:underline">
          privacy policy
        </Link>
        .
      </p>

      <div className="rounded-lg border border-border p-4">
        <p className="text-xs font-semibold text-muted-foreground">After registration</p>
        <div className="mt-3 flex items-center justify-between">
          {[
            ...ONBOARDING_STEPS,
            {
              icon: asSeller ? Store : ShoppingBag,
              label: asSeller ? 'Start selling' : 'Start browsing',
            },
          ].map((step, index, all) => {
            const Icon = step.icon;
            return (
              <div key={step.label} className="flex items-center">
                <div className="flex flex-col items-center gap-1.5 text-center">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand/10 text-brand">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <span className="max-w-16 text-[11px] leading-tight text-muted-foreground">
                    {step.label}
                  </span>
                </div>
                {index < all.length - 1 && (
                  <span className="mx-1 h-px w-4 shrink-0 bg-border sm:w-6" aria-hidden="true" />
                )}
              </div>
            );
          })}
        </div>
        <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
          <Lock className="h-3 w-3 shrink-0" aria-hidden="true" />
          Your identity details are stored encrypted and only used to verify you.
        </p>
      </div>
    </form>
  );
}
