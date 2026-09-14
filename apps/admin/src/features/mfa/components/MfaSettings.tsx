'use client';

import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Card, CardContent, Field, fieldAria, Input, Spinner } from '@trustlens/ui';
import QRCode from 'qrcode';
import { useEffect, useState } from 'react';
import {
  useBeginMfaEnrollment,
  useConfirmMfaEnrollment,
  useDisableMfa,
  useMfaStatus,
} from '../hooks/use-mfa';

export function MfaSettings() {
  const { data: status, isPending } = useMfaStatus();

  if (isPending) {
    return (
      <div className="flex justify-center p-8">
        <Spinner label="Loading MFA status" />
      </div>
    );
  }
  if (!status) {
    return <Alert tone="error">Unable to load MFA status.</Alert>;
  }

  return (
    <Card>
      <CardContent className="space-y-4 pt-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="font-medium">Two-factor authentication</p>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {status.enabled
                ? 'Enabled - an authenticator app code is required at sign-in.'
                : status.required
                  ? 'Not yet enabled, but required for your role on this deployment.'
                  : 'Not enabled.'}
            </p>
          </div>
          <span
            className={
              status.enabled
                ? 'rounded-full bg-risk-low-bg px-2 py-0.5 text-xs font-medium text-risk-low'
                : 'rounded-full bg-risk-unknown-bg px-2 py-0.5 text-xs font-medium text-risk-unknown'
            }
          >
            {status.enabled ? 'Enabled' : 'Disabled'}
          </span>
        </div>

        {status.enabled ? <DisableMfaFlow /> : <EnrollMfaFlow />}
      </CardContent>
    </Card>
  );
}

function EnrollMfaFlow() {
  const begin = useBeginMfaEnrollment();
  const confirm = useConfirmMfaEnrollment();
  const [pending, setPending] = useState<{ secret: string; provisioningUri: string } | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);

  useEffect(() => {
    if (!pending) return;
    let cancelled = false;
    void QRCode.toDataURL(pending.provisioningUri, { width: 200, margin: 1 }).then((url) => {
      if (!cancelled) setQrDataUrl(url);
    });
    return () => {
      cancelled = true;
    };
  }, [pending]);

  async function handleBegin() {
    setError(null);
    try {
      const result = await begin.mutateAsync();
      setPending(result);
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  async function handleConfirm() {
    setError(null);
    try {
      const result = await confirm.mutateAsync(code);
      setRecoveryCodes(result.recoveryCodes);
      setPending(null);
      setQrDataUrl(null);
      setCode('');
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  if (recoveryCodes) {
    return (
      <div className="space-y-3 rounded-lg border border-brand bg-brand/5 p-4">
        <p className="font-medium">MFA enabled. Save these recovery codes now.</p>
        <p className="text-sm text-muted-foreground">
          Each works once, if you lose access to your authenticator app. They will not be shown
          again.
        </p>
        <div className="grid grid-cols-2 gap-2 font-mono text-sm">
          {recoveryCodes.map((rc) => (
            <div key={rc} className="rounded-md bg-muted px-2 py-1">
              {rc}
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!pending) {
    return (
      <div className="space-y-2">
        {error && <Alert tone="error">{error}</Alert>}
        <Button disabled={begin.isPending} onClick={() => void handleBegin()}>
          {begin.isPending ? 'Starting…' : 'Enable two-factor authentication'}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-lg border border-border p-4">
      <p className="text-sm text-muted-foreground">
        Scan this with an authenticator app (Google Authenticator, 1Password, Authy), then enter the
        6-digit code it shows.
      </p>
      {qrDataUrl ? (
        <img
          src={qrDataUrl}
          alt="MFA enrollment QR code"
          className="mx-auto"
          width={200}
          height={200}
        />
      ) : (
        <div className="flex justify-center py-4">
          <Spinner label="Generating QR code" />
        </div>
      )}
      <p className="text-center text-xs text-muted-foreground">
        Can&apos;t scan? Enter this code manually:{' '}
        <code className="rounded bg-muted px-1 py-0.5">{pending.secret}</code>
      </p>
      <Field htmlFor="mfa-confirm-code" label="Code">
        <Input
          {...fieldAria('mfa-confirm-code')}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          inputMode="numeric"
          maxLength={6}
          placeholder="123456"
        />
      </Field>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="flex gap-2">
        <Button
          disabled={code.length !== 6 || confirm.isPending}
          onClick={() => void handleConfirm()}
        >
          {confirm.isPending ? 'Confirming…' : 'Confirm and enable'}
        </Button>
        <Button
          variant="outline"
          onClick={() => {
            setPending(null);
            setQrDataUrl(null);
          }}
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}

function DisableMfaFlow() {
  const disable = useDisableMfa();
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  async function handleDisable() {
    setError(null);
    try {
      await disable.mutateAsync(password);
      setConfirming(false);
      setPassword('');
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  if (!confirming) {
    return (
      <Button variant="destructive" onClick={() => setConfirming(true)}>
        Disable two-factor authentication
      </Button>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-destructive/40 p-4">
      <Field htmlFor="mfa-disable-password" label="Confirm your password" required>
        <Input
          {...fieldAria('mfa-disable-password')}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </Field>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="flex gap-2">
        <Button
          variant="destructive"
          disabled={!password || disable.isPending}
          onClick={() => void handleDisable()}
        >
          {disable.isPending ? 'Disabling…' : 'Confirm disable'}
        </Button>
        <Button variant="outline" onClick={() => setConfirming(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
