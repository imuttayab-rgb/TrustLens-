'use client';

import { useConfirmHandover, useMyTransactions, useRaiseDispute } from '@/features/commerce';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Card, CardContent, Field, Spinner } from '@trustlens/ui';
import { useParams } from 'next/navigation';
import { useState } from 'react';

const DISPUTE_CATEGORY_LABELS: Record<string, string> = {
  SCAM_OR_FRAUD: 'Scam or fraud',
  PROHIBITED_ITEM: 'Prohibited item',
  HARASSMENT: 'Harassment or abuse',
  MISLEADING_LISTING: 'Not as described',
  OTHER: 'Something else',
};

const MIN_DISPUTE_DESCRIPTION_CHARS = 10;

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
      ) : transaction.status === 'DISPUTED' ? (
        <Alert tone="info">
          This deal is under dispute. Staff are reviewing it - you&apos;ll be notified once
          it&apos;s resolved.
        </Alert>
      ) : done || transaction.status === 'HANDED_OVER' ? (
        <>
          <Alert tone="success">Handover confirmed.</Alert>
          <DisputeSection transactionId={transactionId} />
        </>
      ) : transaction.status === 'COMPLETED' || transaction.status === 'CANCELLED' ? (
        <Alert tone="info">This deal is already closed.</Alert>
      ) : (
        <>
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
          <DisputeSection transactionId={transactionId} />
        </>
      )}
    </main>
  );
}

/** The escape hatch when the two sides disagree about what happened
 * (OPS-01) - freezes the transaction and opens it in the staff reports
 * queue, the same one listing/seller/message reports already go through. */
function DisputeSection({ transactionId }: { transactionId: string }) {
  const raiseDispute = useRaiseDispute();
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState('SCAM_OR_FRAUD');
  const [description, setDescription] = useState('');
  const [failure, setFailure] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  if (done) {
    return (
      <Alert tone="success" className="text-sm">
        Dispute raised. This deal is now frozen while staff review it.
      </Alert>
    );
  }

  if (!open) {
    return (
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        Something wrong? Raise a dispute
      </Button>
    );
  }

  const trimmed = description.trim();
  const canSubmit = trimmed.length >= MIN_DISPUTE_DESCRIPTION_CHARS;

  async function submit() {
    setFailure(null);
    try {
      await raiseDispute.mutateAsync({ transactionId, category, description });
      setDone(true);
    } catch (err) {
      setFailure(toApiError(err).message);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3 pt-5">
        <Field htmlFor="dispute-category" label="What's wrong?">
          <select
            id="dispute-category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {Object.entries(DISPUTE_CATEGORY_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field
          htmlFor="dispute-description"
          label="Describe what happened"
          hint={`${trimmed.length} / ${MIN_DISPUTE_DESCRIPTION_CHARS} characters minimum`}
        >
          <textarea
            id="dispute-description"
            rows={3}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </Field>
        {failure && <Alert tone="error">{failure}</Alert>}
        <div className="flex gap-2">
          <Button
            size="sm"
            disabled={!canSubmit || raiseDispute.isPending}
            onClick={() => void submit()}
          >
            {raiseDispute.isPending ? 'Submitting…' : 'Raise dispute'}
          </Button>
          <Button size="sm" variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
