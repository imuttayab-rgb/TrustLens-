'use client';

import { Alert, Button, Spinner } from '@trustlens/ui';
import QRCode from 'qrcode';
import { useEffect, useState } from 'react';

/**
 * The QR check-in (QR-01). The code is a plain deep link to
 * `/dashboard/handover/{transactionId}`, not a signed or time-limited
 * token - the transaction's own open/closed state is what bounds how long
 * an old code stays meaningful (see `ConfirmHandover`'s docstring). Whoever
 * opens the link, signed in as a party to that deal, can confirm it.
 */
export function HandoverQrCode({ transactionId }: { transactionId: string }) {
  const [showing, setShowing] = useState(false);
  const [dataUrl, setDataUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!showing) return;
    let cancelled = false;
    const url = `${window.location.origin}/dashboard/handover/${transactionId}`;
    QRCode.toDataURL(url, { width: 220, margin: 1 })
      .then((data) => {
        if (!cancelled) setDataUrl(data);
      })
      .catch(() => {
        if (!cancelled) setError('Could not generate the QR code.');
      });
    return () => {
      cancelled = true;
    };
  }, [showing, transactionId]);

  if (!showing) {
    return (
      <Button size="sm" variant="outline" onClick={() => setShowing(true)}>
        Show handover QR
      </Button>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-border p-3 text-center">
      <p className="text-sm text-muted-foreground">
        Have the other party scan this with their phone's camera to confirm the handover.
      </p>
      {error && <Alert tone="error">{error}</Alert>}
      {dataUrl ? (
        <img
          src={dataUrl}
          alt="Handover confirmation QR code"
          className="mx-auto"
          width={220}
          height={220}
        />
      ) : (
        <div className="flex justify-center py-4">
          <Spinner label="Generating QR code" />
        </div>
      )}
      <Button size="sm" variant="outline" onClick={() => setShowing(false)}>
        Hide
      </Button>
    </div>
  );
}
