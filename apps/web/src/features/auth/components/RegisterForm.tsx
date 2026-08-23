'use client';

import { api } from '@/lib/api/client';
import { setAccessToken } from '@/lib/auth/session';
import { useApiForm } from '@/lib/forms/use-api-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { registerSchema, type RegisterInput } from '@trustlens/validation';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useForm } from 'react-hook-form';

export function RegisterForm({ className }: { className?: string }) {
  const router = useRouter();

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterInput>({
    resolver: zodResolver(registerSchema),
    defaultValues: { asSeller: true, acceptedTerms: false as unknown as true },
  });

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
      router.push('/login');
    }
  });

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
        <Input
          {...fieldAria('password', errors.password?.message, 'hint')}
          type="password"
          autoComplete="new-password"
          {...register('password')}
        />
      </Field>

      <Field
        htmlFor="confirmPassword"
        label="Confirm password"
        required
        error={errors.confirmPassword?.message}
      >
        <Input
          {...fieldAria('confirmPassword', errors.confirmPassword?.message)}
          type="password"
          autoComplete="new-password"
          {...register('confirmPassword')}
        />
      </Field>

      <div className="space-y-3 pt-1">
        <label className="flex cursor-pointer items-start gap-3 text-sm">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 shrink-0 rounded border-input text-primary focus-visible:ring-2 focus-visible:ring-ring"
            {...register('asSeller')}
          />
          <span>
            I want to sell, and to earn a Trust Score
            <span className="block text-muted-foreground">
              Buyers can look up your score before dealing with you.
            </span>
          </span>
        </label>

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
          <p id="terms-error" role="alert" className="text-sm text-destructive">
            {errors.acceptedTerms.message}
          </p>
        )}
      </div>

      {formError && (
        <Alert tone="error" requestId={formError.requestId}>
          {formError.message}
        </Alert>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Creating your account…' : 'Create account'}
      </Button>
    </form>
  );
}
