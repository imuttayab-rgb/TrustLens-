'use client';

import { api } from '@/lib/api/client';
import { setAccessToken } from '@/lib/auth/session';
import { zodResolver } from '@hookform/resolvers/zod';
import { toApiError } from '@trustlens/api-client';
import { Button } from '@trustlens/ui';
import { loginSchema, type LoginInput } from '@trustlens/validation';
import { cn } from '@trustlens/utils';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useForm } from 'react-hook-form';

export function LoginForm({ className }: { className?: string }) {
  const router = useRouter();
  const [formError, setFormError] = useState<{ message: string; requestId?: string } | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>({ resolver: zodResolver(loginSchema) });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const result = await api.POST('/api/v1/auth/login', { body: values });
      if (result.error) throw result.error;

      const token = (result.data as { data: { accessToken: string } }).data.accessToken;
      setAccessToken(token);
      router.push('/dashboard');
    } catch (raw) {
      const error = toApiError(raw);
      // Map field errors from the RFC 9457 `errors[]` array straight onto the
      // form inputs, so the user sees them where they typed.
      for (const [field, message] of Object.entries(error.fieldErrors)) {
        setError(field as keyof LoginInput, { message });
      }
      if (Object.keys(error.fieldErrors).length === 0) {
        setFormError({ message: error.message, requestId: error.requestId });
      }
    }
  });

  return (
    <form onSubmit={onSubmit} className={cn('space-y-4', className)} noValidate>
      <div>
        <label htmlFor="email" className="block text-sm font-medium">
          Email address
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? 'email-error' : undefined}
          className="border-input focus-visible:ring-ring mt-1 h-10 w-full rounded-md border px-3 focus-visible:outline-none focus-visible:ring-2"
          {...register('email')}
        />
        {errors.email && (
          <p id="email-error" role="alert" className="text-destructive mt-1 text-sm">
            {errors.email.message}
          </p>
        )}
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium">
          Password
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          aria-invalid={!!errors.password}
          aria-describedby={errors.password ? 'password-error' : undefined}
          className="border-input focus-visible:ring-ring mt-1 h-10 w-full rounded-md border px-3 focus-visible:outline-none focus-visible:ring-2"
          {...register('password')}
        />
        {errors.password && (
          <p id="password-error" role="alert" className="text-destructive mt-1 text-sm">
            {errors.password.message}
          </p>
        )}
      </div>

      {formError && (
        <div role="alert" className="bg-risk-high-bg text-risk-high rounded-md p-3 text-sm">
          <p>{formError.message}</p>
          {/* Surfacing the request id turns "it didn't work" into one log query. */}
          {formError.requestId && (
            <p className="mt-1 font-mono text-xs opacity-80">Reference: {formError.requestId}</p>
          )}
        </div>
      )}

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Signing in…' : 'Sign in'}
      </Button>
    </form>
  );
}
