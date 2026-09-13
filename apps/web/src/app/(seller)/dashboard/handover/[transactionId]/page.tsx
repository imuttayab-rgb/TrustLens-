'use client';

import { useConfirmHandover, useMyTransactions } from '@/features/commerce';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Card, CardContent, Spinner } from '@trustlens/ui';
import { useParams } from 'next/navigation';
import { useState } from 'react';

/**
 * Where a handover QR code (QR-01) deep-links to. Whoever scans it lands
 * here signed in as themselves; confirming just needs them to be a party
 * to this transaction, same as every other commerce action - the QR code
 * itself carries no separate proof.
 */
export default function HandoverConfirmPage() {
  const { transactionId } = useParams<{ transactionId: string }>();
  const { data: transactions, isPending } = useMyTransactions();
  const confirmHandover = useConfirmHandover();
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const transaction = transactions?.find((t) => t.id === transactionId);

  async function handleConfirm() {
    setError(null);
    try {
      await confirmHandover.mutateAsync(transactionId);
      setDone(true);
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  return (
    <main className="mx-auto max-w-md space-y-4 p-6 sm:p-8">
      <h1 className="text-xl font-bold">Confirm handover</h1>

      {isPending ? (
        <div className="flex justify-center py-8">
          <Spinner label="Loading" />
        </div>
      ) : !transaction ? (
        <Alert tone="error">
          This transaction isn&apos;t yours, doesn&apos;t exist, or you need to sign in first.
        </Alert>
      ) : done || transaction.status === 'HANDED_OVER' ? (
        <Alert tone="success">Handover confirmed.</Alert>
      ) : transaction.status === 'COMPLETED' || transaction.status === 'CANCELLED' ? (
        <Alert tone="info">This deal is already closed.</Alert>
      ) : (
        <Card>
          <CardContent className="space-y-3 pt-5 text-center">
            <p className="text-sm text-muted-foreground">
              Confirming means you and the other party have met and the item has changed hands.
            </p>
            {error && <Alert tone="error">{error}</Alert>}
            <Button disabled={confirmHandover.isPending} onClick={() => void handleConfirm()}>
              {confirmHandover.isPending ? 'Confirming…' : 'Confirm handover'}
            </Button>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
