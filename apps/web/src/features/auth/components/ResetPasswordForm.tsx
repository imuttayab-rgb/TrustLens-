'use client';

import { api } from '@/lib/api/client';
import { useApiForm } from '@/lib/forms/use-api-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { resetPasswordSchema } from '@trustlens/validation';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import type { z } from 'zod';

type ResetInput = z.infer<typeof resetPasswordSchema>;

export function ResetPasswordForm({ className }: { className?: string }) {
  const router = useRouter();
  const token = useSearchParams().get('token') ?? '';
  const [done, setDone] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ResetInput>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { token },
  });

  const { submit, formError } = useApiForm<ResetInput>(setError);

  const onSubmit = handleSubmit(async (values) => {
    const ok = await submit(async () => {
      const result = await api.POST('/api/v1/auth/reset-password', {
        body: { token: values.token, password: values.password },
      });
      if (result.error) throw toApiError(result.error);
    });
    if (ok) setDone(true);
  });

  if (!token) {
    return (
      <Alert tone="error" title="This link is incomplete" className={className}>
        Request a{' '}
        <Link href="/forgot-password" className="underline underline-offset-4">
          new reset link
        </Link>
        .
      </Alert>
    );
  }

  if (done) {
    return (
      <div className={cn('space-y-4', className)}>
        <Alert tone="success" title="Password changed">
          Every other session has been signed out.
        </Alert>
        <Button size="lg" className="w-full" onClick={() => router.push('/login')}>
          Sign in
        </Button>
      </div>
    );
  }

  return (
    <form
      onSubmit={(event) => void onSubmit(event)}
      className={cn('space-y-4', className)}
      noValidate
    >
      <input type="hidden" {...register('token')} />

      <Field
        htmlFor="password"
        label="New password"
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
        label="Confirm new password"
        error={errors.confirmPassword?.message}
      >
        <Input
          {...fieldAria('confirmPassword', errors.confirmPassword?.message)}
          type="password"
          autoComplete="new-password"
          {...register('confirmPassword')}
        />
      </Field>

      {formError && (
        <Alert tone="error" requestId={formError.requestId}>
          {formError.message}
        </Alert>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Saving…' : 'Set new password'}
      </Button>
    </form>
  );
}
