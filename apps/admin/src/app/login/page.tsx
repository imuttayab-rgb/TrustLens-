'use client';

import { api } from '@/lib/api/client';
import { setAccessToken } from '@/lib/auth/session';
import { useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import { Alert, Ambient, Button, Field, fieldAria, Input } from '@trustlens/ui';
import { ShieldCheck } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';

function LoginForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; requestId: string | undefined } | null>(
    null,
  );

  // Only ever redirect within this app - an open redirect on a staff login is
  // a phishing gift, and this one reaches identity documents.
  const raw = params.get('next');
  const next = raw && raw.startsWith('/') && !raw.startsWith('//') ? raw : '/';

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.POST('/api/v1/auth/login', { body: { email, password } });
      if (result.error) throw toApiError(result.error);
      setAccessToken((result.data as { data: { accessToken: string } }).data.accessToken);
      // The guard already asked "who is this?" before the redirect here and
      // cached the answer: nobody. Without dropping that, it re-reads the
      // cached null and bounces straight back to this page.
      await queryClient.invalidateQueries({ queryKey: ['me'] });
      router.replace(next);
      router.refresh();
    } catch (raw_) {
      const apiError = toApiError(raw_);
      setError({ message: apiError.message, requestId: apiError.requestId });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="space-y-4" noValidate>
      <Field htmlFor="email" label="Email address">
        <Input
          {...fieldAria('email')}
          type="email"
          inputMode="email"
          autoComplete="email"
          autoCapitalize="none"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </Field>

      <Field htmlFor="password" label="Password">
        <Input
          {...fieldAria('password')}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </Field>

      {error && (
        <Alert tone="error" requestId={error.requestId}>
          {error.message}
        </Alert>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={busy}>
        {busy ? 'Signing in…' : 'Sign in'}
      </Button>
    </form>
  );
}

export default function AdminLoginPage() {
  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden px-6">
      <Ambient intensity="full" />
      <div className="w-full max-w-sm rounded-2xl border border-border/70 bg-card/60 p-7 backdrop-blur-xl">
        <div className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand to-brand-2">
            <ShieldCheck
              className="h-4 w-4 text-[hsl(var(--background))]"
              strokeWidth={2.5}
              aria-hidden="true"
            />
          </span>
          <span className="font-bold tracking-tight">TrustLens Admin</span>
        </div>
        <p className="mb-6 mt-3 text-sm text-muted-foreground">
          Staff access only. Every decision made here is recorded against your account.
        </p>
        <Suspense fallback={<div className="h-56" aria-hidden="true" />}>
          <LoginForm />
        </Suspense>
      </div>
    </div>
  );
}
