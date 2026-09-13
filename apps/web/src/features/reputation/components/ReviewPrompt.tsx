'use client';

import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Input, Spinner } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { Star } from 'lucide-react';
import { useState } from 'react';
import { useCreateReview, useMyReviewForTransaction } from '../hooks/use-reputation';

/**
 * A blind review of the other party on a completed deal - shown in the
 * message thread once a transaction is done. Blind: this only ever shows
 * the reviewer their own submission, never whether or what the other side
 * has left, until both sides' reviews are visible together on the public
 * seller page (list_visible_for_seller enforces that server-side).
 */
export function ReviewPrompt({ transactionId }: { transactionId: string }) {
  const { data: review, isPending } = useMyReviewForTransaction(transactionId);
  const createReview = useCreateReview(transactionId);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (isPending) {
    return <Spinner label="Loading review status" />;
  }

  if (review) {
    return (
      <div className="rounded-lg border border-border p-3 text-sm">
        <p className="font-medium">You reviewed this deal</p>
        <StarRow value={review.rating} />
        {review.comment && <p className="mt-1 text-muted-foreground">{review.comment}</p>}
      </div>
    );
  }

  async function handleSubmit() {
    if (rating < 1) {
      setError('Pick a rating.');
      return;
    }
    setError(null);
    try {
      const trimmed = comment.trim();
      await createReview.mutateAsync(trimmed ? { rating, comment: trimmed } : { rating });
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  return (
    <div className="space-y-2 rounded-lg border border-border p-3 text-sm">
      <p className="font-medium">How did this deal go?</p>
      <StarRow value={rating} onChange={setRating} />
      <Input
        value={comment}
        onChange={(event) => setComment(event.target.value)}
        placeholder="Leave a comment (optional)"
      />
      {error && <Alert tone="error">{error}</Alert>}
      <Button size="sm" disabled={createReview.isPending} onClick={() => void handleSubmit()}>
        {createReview.isPending ? 'Submitting…' : 'Submit review'}
      </Button>
    </div>
  );
}

function StarRow({ value, onChange }: { value: number; onChange?: (rating: number) => void }) {
  return (
    <div className="flex gap-1" role={onChange ? 'radiogroup' : undefined} aria-label="Rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={!onChange}
          aria-label={`${n} star${n === 1 ? '' : 's'}`}
          aria-pressed={onChange ? n <= value : undefined}
          onClick={() => onChange?.(n)}
          className={cn(!onChange && 'cursor-default')}
        >
          <Star
            className={cn(
              'h-5 w-5',
              n <= value ? 'fill-current text-amber-500' : 'text-muted-foreground',
            )}
            aria-hidden="true"
          />
        </button>
      ))}
    </div>
  );
}
