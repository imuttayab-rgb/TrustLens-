/** Reusable UI rendering and interaction component: VerifyEmailPanel. */
'use client';

import { api } from '@/lib/api/client';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Spinner } from '@trustlens/ui';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

type State =
  | { kind: 'missing' }
  | { kind: 'verifying' }
  | { kind: 'ok' }
  | { kind: 'failed'; message: string; requestId: string | undefined };

export function VerifyEmailPanel() {
  const token = useSearchParams().get('token');
  const [state, setState] = useState<State>(token ? { kind: 'verifying' } : { kind: 'missing' });
  // React 19 runs effects twice in development. Without this guard the token
  // is spent by the first call and the second reports "already used".
  const attempted = useRef(false);

  useEffect(() => {
    if (!token || attempted.current) return;
    attempted.current = true;

    void (async () => {
      try {
        const result = await api.POST('/api/v1/auth/verify-email', { body: { token } });
        if (result.error) throw toApiError(result.error);
        setState({ kind: 'ok' });
      } catch (raw) {
        const error = toApiError(raw);
        setState({ kind: 'failed', message: error.message, requestId: error.requestId });
      }
    })();
  }, [token]);

  if (state.kind === 'missing') {
    return (
      <Alert tone="warning" title="This link is incomplete">
        Open the link from your email exactly as it was sent.
      </Alert>
    );
  }

  if (state.kind === 'verifying') {
    return (
      <div className="flex items-center gap-3 text-sm">
        <Spinner label="Confirming your email address" />
        <span className="text-muted-foreground">Confirming your email address…</span>
      </div>
    );
  }

  if (state.kind === 'ok') {
    return (
      <div className="space-y-4">
        <Alert tone="success" title="Email confirmed">
          That is one verification check complete.
        </Alert>
        <Button size="lg" className="w-full" asChild>
          <Link href="/dashboard">Continue to your dashboard</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Alert tone="error" title="We could not confirm that link" requestId={state.requestId}>
        {state.message} Links expire, and each one works only once.
      </Alert>
      <Button variant="outline" size="lg" className="w-full" asChild>
        <Link href="/dashboard/verification/email">Send a new link</Link>
      </Button>
    </div>
  );
}
