'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { setAccessToken } from '@/lib/auth/session';
import { useApiForm } from '@/lib/forms/use-api-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { loginSchema, type LoginInput } from '@trustlens/validation';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';

/** Only ever redirect within this app - an open redirect is a phishing gift. */
function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//')) return '/dashboard';
  return raw;
}

export function LoginForm({ className }: { className?: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const next = safeNext(params.get('next'));

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>({ resolver: zodResolver(loginSchema) });

  const { submit, formError } = useApiForm<LoginInput>(setError);

  const onSubmit = handleSubmit(async (values) => {
    const ok = await submit(async () => {
      const result = await api.POST('/api/v1/auth/login', { body: values });
      if (result.error) throw toApiError(result.error);
      const token = (result.data as { data: { accessToken: string } }).data.accessToken;
      setAccessToken(token);
    });

    if (ok) {
      // The guard may already have cached "not signed in" before redirecting
      // here; without dropping it the dashboard bounces straight back.
      await queryClient.invalidateQueries({ queryKey: qk.me });
      router.push(next);
      // The dashboard renders on the server from the session cookie, so its
      // cached payload has to be dropped or the first paint is the
      // logged-out one.
      router.refresh();
    }
  });

  return (
    <form
      onSubmit={(event) => void onSubmit(event)}
      className={cn('space-y-4', className)}
      noValidate
    >
      <Field htmlFor="email" label="Email address" error={errors.email?.message}>
        <Input
          {...fieldAria('email', errors.email?.message)}
          type="email"
          inputMode="email"
          autoComplete="email"
          autoCapitalize="none"
          {...register('email')}
        />
      </Field>

      <Field htmlFor="password" label="Password" error={errors.password?.message}>
        <Input
          {...fieldAria('password', errors.password?.message)}
          type="password"
          autoComplete="current-password"
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
        <Alert tone="error" requestId={formError.requestId}>
          {formError.message}
        </Alert>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Signing in…' : 'Sign in'}
      </Button>
    </form>
  );
}
