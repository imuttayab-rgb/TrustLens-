'use client';

import { api } from '@/lib/api/client';
import type { FormError } from '@/lib/forms/use-api-form';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button } from '@trustlens/ui';
import { useState } from 'react';

export function EmailVerification({ email, verified }: { email: string; verified: boolean }) {
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<FormError | null>(null);

  if (verified) {
    return (
      <Alert tone="success" title="Email verified">
        {email} is confirmed.
      </Alert>
    );
  }

  async function resend() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.POST('/api/v1/auth/resend-verification-email', {
        body: { email },
      });
      if (result.error) throw toApiError(result.error);
      setSent(true);
    } catch (raw) {
      const apiError = toApiError(raw);
      setError({ message: apiError.message, requestId: apiError.requestId });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        We sent a confirmation link to <span className="font-medium text-foreground">{email}</span>.
        Open it to complete this check.
      </p>

      {sent && <Alert tone="success">A new link is on its way.</Alert>}
      {error && (
        <Alert tone="error" requestId={error.requestId}>
          {error.message}
        </Alert>
      )}

      <Button variant="outline" className="w-full" disabled={busy} onClick={() => void resend()}>
        {busy ? 'Sending…' : 'Send the link again'}
      </Button>

      <p className="text-xs text-muted-foreground">
        Nothing arrives? Check your spam folder. Temporary or disposable addresses score lower and
        may not receive mail at all.
      </p>
    </div>
  );
}
