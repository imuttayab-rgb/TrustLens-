'use client';

import { ReviewPrompt } from '@/features/reputation';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input, Spinner } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { useState } from 'react';
import { HandoverQrCode } from './HandoverQrCode';
import {
  useCancelTransaction,
  useCompleteTransaction,
  useCreateOffer,
  useMyTransactions,
  useOffers,
  useRespondToOffer,
  type Offer,
  type Transaction,
} from '../hooks/use-commerce';

const STATUS_LABEL: Record<Offer['status'], string> = {
  PENDING: 'Pending',
  ACCEPTED: 'Accepted',
  REJECTED: 'Rejected',
  COUNTERED: 'Countered',
  EXPIRED: 'Expired',
};

const OPEN_TRANSACTION_STATUSES: readonly Transaction['status'][] = [
  'INITIATED',
  'AGREED',
  'MEETUP_PLANNED',
  'HANDED_OVER',
];

function formatMoney(amount: number, currency: string) {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

/**
 * Offer history plus a "make an offer" form, for one conversation. Shown
 * inside the message thread so negotiating an offer reads like part of the
 * same conversation rather than a separate flow.
 */
export function OfferPanel({
  conversationId,
  listingId,
  currentUserId,
}: {
  conversationId: string;
  listingId: string;
  currentUserId: string;
}) {
  const { data: offers, isPending } = useOffers(conversationId);
  const { data: transactions } = useMyTransactions();
  const createOffer = useCreateOffer(conversationId);
  const respondToOffer = useRespondToOffer(conversationId);
  const [showForm, setShowForm] = useState(false);
  const [amount, setAmount] = useState('');
  const [message, setMessage] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [respondError, setRespondError] = useState<string | null>(null);

  const openOffer = offers?.find((offer) => offer.status === 'PENDING');
  const history = offers?.filter((offer) => offer.id !== openOffer?.id) ?? [];
  const openTransaction = transactions?.find(
    (txn) => txn.listingId === listingId && OPEN_TRANSACTION_STATUSES.includes(txn.status),
  );
  const completedTransaction = transactions?.find(
    (txn) => txn.listingId === listingId && txn.status === 'COMPLETED',
  );

  async function handleSubmit() {
    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setFormError('Enter an amount greater than zero.');
      return;
    }
    setFormError(null);
    try {
      const trimmedMessage = message.trim();
      await createOffer.mutateAsync(
        trimmedMessage ? { amount: parsed, message: trimmedMessage } : { amount: parsed },
      );
      setAmount('');
      setMessage('');
      setShowForm(false);
    } catch (error) {
      setFormError(toApiError(error).message);
    }
  }

  return (
    <div className="space-y-3 border-b border-border p-3">
      {openTransaction && (
        <TransactionCard transaction={openTransaction} currentUserId={currentUserId} />
      )}
      {completedTransaction && <ReviewPrompt transactionId={completedTransaction.id} />}

      {isPending ? (
        <Spinner label="Loading offers" />
      ) : (
        <>
          {openOffer && !openTransaction && (
            <OfferRow
              offer={openOffer}
              currentUserId={currentUserId}
              highlighted
              onRespond={(accept) => {
                void (async () => {
                  setRespondError(null);
                  try {
                    await respondToOffer.mutateAsync({ offerId: openOffer.id, accept });
                  } catch (error) {
                    setRespondError(toApiError(error).message);
                  }
                })();
              }}
              responding={respondToOffer.isPending}
            />
          )}
          {respondError && <Alert tone="error">{respondError}</Alert>}

          {history.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer text-muted-foreground">
                Offer history ({history.length})
              </summary>
              <div className="mt-2 space-y-2">
                {history.map((offer) => (
                  <OfferRow key={offer.id} offer={offer} currentUserId={currentUserId} />
                ))}
              </div>
            </details>
          )}
        </>
      )}

      {!openOffer &&
        !openTransaction &&
        (showForm ? (
          <div className="space-y-2 rounded-lg border border-border p-3">
            <Field htmlFor="offer-amount" label="Offer amount" required>
              <Input
                {...fieldAria('offer-amount')}
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                placeholder="0.00"
              />
            </Field>
            <Field htmlFor="offer-message" label="Message" hint="Optional">
              <Input
                {...fieldAria('offer-message')}
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="e.g. Can you do this price?"
              />
            </Field>
            {formError && <Alert tone="error">{formError}</Alert>}
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={createOffer.isPending}
                onClick={() => void handleSubmit()}
              >
                {createOffer.isPending ? 'Sending…' : 'Send offer'}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button size="sm" variant="outline" onClick={() => setShowForm(true)}>
            Make an offer
          </Button>
        ))}
    </div>
  );
}

function TransactionCard({
  transaction,
  currentUserId,
}: {
  transaction: Transaction;
  currentUserId: string;
}) {
  const completeTransaction = useCompleteTransaction();
  const cancelTransaction = useCancelTransaction();
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const isSeller = transaction.sellerId === currentUserId;

  async function handleComplete() {
    setError(null);
    try {
      await completeTransaction.mutateAsync(transaction.id);
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  async function handleCancel() {
    setError(null);
    try {
      await cancelTransaction.mutateAsync({ transactionId: transaction.id, reason: reason.trim() });
      setCancelling(false);
      setReason('');
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  return (
    <div className="space-y-2 rounded-lg border border-brand bg-brand/5 p-3 text-sm">
      <p className="font-medium">
        Deal agreed at {formatMoney(transaction.amount, transaction.currency)}
      </p>
      <p className="text-muted-foreground">
        {transaction.status === 'HANDED_OVER'
          ? 'Handover confirmed.'
          : isSeller
            ? 'Mark this done once you hand the item over and get paid.'
            : 'The seller will mark this done once you complete the handover.'}
      </p>
      {transaction.status !== 'HANDED_OVER' && <HandoverQrCode transactionId={transaction.id} />}
      {error && <Alert tone="error">{error}</Alert>}
      {cancelling ? (
        <div className="space-y-2">
          <Field htmlFor="cancel-reason" label="Why are you cancelling?" required>
            <Input
              {...fieldAria('cancel-reason')}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="e.g. Buyer backed out"
            />
          </Field>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="destructive"
              disabled={!reason.trim() || cancelTransaction.isPending}
              onClick={() => void handleCancel()}
            >
              {cancelTransaction.isPending ? 'Cancelling…' : 'Confirm cancel'}
            </Button>
            <Button size="sm" variant="outline" onClick={() => setCancelling(false)}>
              Back
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <Button
            size="sm"
            disabled={completeTransaction.isPending}
            onClick={() => void handleComplete()}
          >
            {completeTransaction.isPending ? 'Marking done…' : 'Mark as done'}
          </Button>
          <Button size="sm" variant="outline" onClick={() => setCancelling(true)}>
            Cancel deal
          </Button>
        </div>
      )}
    </div>
  );
}

function OfferRow({
  offer,
  currentUserId,
  highlighted,
  onRespond,
  responding,
}: {
  offer: Offer;
  currentUserId: string;
  highlighted?: boolean;
  onRespond?: (accept: boolean) => void;
  responding?: boolean;
}) {
  const isMine = offer.offeredBy === currentUserId;
  const canRespond = onRespond && offer.status === 'PENDING' && !isMine;

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 rounded-lg border p-3 text-sm',
        highlighted ? 'border-brand bg-brand/5' : 'border-border',
      )}
    >
      <div>
        <p className="font-medium">{formatMoney(offer.amount, offer.currency)}</p>
        <p className="text-muted-foreground">
          {isMine ? 'You offered' : 'They offered'} · {STATUS_LABEL[offer.status]}
        </p>
        {offer.message && (
          <p className="mt-1 text-muted-foreground">&ldquo;{offer.message}&rdquo;</p>
        )}
      </div>
      {canRespond && (
        <div className="flex shrink-0 gap-2">
          <Button size="sm" disabled={responding} onClick={() => onRespond(true)}>
            Accept
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={responding}
            onClick={() => onRespond(false)}
          >
            Reject
          </Button>
        </div>
      )}
    </div>
  );
}
