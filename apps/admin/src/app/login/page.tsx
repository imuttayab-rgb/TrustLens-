'use client';

import { api } from '@/lib/api/client';
import { setAccessToken } from '@/lib/auth/session';
import { useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import { Alert, Ambient, Button, Field, fieldAria, Input, PasswordInput } from '@trustlens/ui';
import { ShieldCheck } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';

interface LoginSuccess {
  accessToken: string;
}

interface MfaChallenge {
  mfaRequired: true;
  mfaToken: string;
}

function isMfaChallenge(data: LoginSuccess | MfaChallenge): data is MfaChallenge {
  return 'mfaRequired' in data && data.mfaRequired;
}

function LoginForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; requestId: string | undefined } | null>(
    null,
  );

  // Only ever redirect within this app - an open redirect on a staff login is
  // a phishing gift, and this one reaches identity documents.
  const raw = params.get('next');
  const next = raw && raw.startsWith('/') && !raw.startsWith('//') ? raw : '/';

  async function finishLogin() {
    // The guard already asked "who is this?" before the redirect here and
    // cached the answer: nobody. Without dropping that, it re-reads the
    // cached null and bounces straight back to this page.
    await queryClient.invalidateQueries({ queryKey: ['me'] });
    router.replace(next);
    router.refresh();
  }

  async function submitPassword(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.POST('/api/v1/auth/login', { body: { email, password } });
      if (result.error) throw toApiError(result.error);
      const data = (result.data as { data: LoginSuccess | MfaChallenge }).data;
      if (isMfaChallenge(data)) {
        setMfaToken(data.mfaToken);
      } else {
        setAccessToken(data.accessToken);
        await finishLogin();
      }
    } catch (raw_) {
      const apiError = toApiError(raw_);
      setError({ message: apiError.message, requestId: apiError.requestId });
    } finally {
      setBusy(false);
    }
  }

  async function submitMfaCode(event: React.FormEvent) {
    event.preventDefault();
    if (!mfaToken) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.POST('/api/v1/auth/mfa/verify', {
        body: { mfaToken, code },
      });
      if (result.error) throw toApiError(result.error);
      setAccessToken((result.data as { data: LoginSuccess }).data.accessToken);
      await finishLogin();
    } catch (raw_) {
      const apiError = toApiError(raw_);
      setError({ message: apiError.message, requestId: apiError.requestId });
    } finally {
      setBusy(false);
    }
  }

  if (mfaToken) {
    return (
      <form onSubmit={(e) => void submitMfaCode(e)} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">
          Enter the code from your authenticator app, or one of your recovery codes.
        </p>
        <Field htmlFor="mfa-code" label="Authentication code">
          <Input
            {...fieldAria('mfa-code')}
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </Field>

        {error && (
          <Alert tone="error" requestId={error.requestId}>
            {error.message}
          </Alert>
        )}

        <Button type="submit" size="lg" className="w-full" disabled={busy || !code}>
          {busy ? 'Verifying…' : 'Verify'}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => {
            setMfaToken(null);
            setCode('');
            setError(null);
          }}
        >
          Back
        </Button>
      </form>
    );
  }

  return (
    <form onSubmit={(e) => void submitPassword(e)} className="space-y-4" noValidate>
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
        <PasswordInput
          {...fieldAria('password')}
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
