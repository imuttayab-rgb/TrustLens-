'use client';

import { api } from '@/lib/api/client';
import { useApiForm } from '@/lib/forms/use-api-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { emailSchema } from '@trustlens/validation';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

const schema = z.object({ email: emailSchema });
type Input_ = z.infer<typeof schema>;

export function ForgotPasswordForm({ className }: { className?: string }) {
  const [sent, setSent] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Input_>({ resolver: zodResolver(schema) });

  const { submit, formError } = useApiForm<Input_>(setError);

  const onSubmit = handleSubmit(async (values) => {
    const ok = await submit(async () => {
      const result = await api.POST('/api/v1/auth/forgot-password', { body: values });
      if (result.error) throw toApiError(result.error);
    });
    if (ok) setSent(true);
  });

  // Deliberately identical whether or not the address exists. Saying "no such
  // account" would turn this form into a free account-enumeration oracle.
  if (sent) {
    return (
      <Alert tone="success" title="Check your email" className={className}>
        If that address has an account, a reset link is on its way. The link expires shortly.
      </Alert>
    );
  }

  return (
    <form
      onSubmit={(event) => void onSubmit(event)}
      className={cn('space-y-4', className)}
      noValidate
    >
      <Field
        htmlFor="email"
        label="Email address"
        error={errors.email?.message}
        hint="We'll send a link to reset your password."
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

      {formError && (
        <Alert tone="error" requestId={formError.requestId}>
          {formError.message}
        </Alert>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Sending…' : 'Send reset link'}
      </Button>
    </form>
  );
}
