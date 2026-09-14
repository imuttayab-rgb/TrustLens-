'use client';

import type { useBusinessReview } from '../hooks/use-business-review';
import { Alert, Spinner } from '@trustlens/ui';

/** The registration document and declared business details, via the
 * short-lived signed URL `GET /admin/sellers/{id}/business-review` returns.
 * There is no automated verdict to show here - a business submission
 * always goes straight to a human. */
export function BusinessEvidence({ business }: { business: ReturnType<typeof useBusinessReview> }) {
  if (business.isPending) return <Spinner label="Loading business evidence" />;
  if (business.error) {
    return <Alert tone="error">Business evidence could not be loaded.</Alert>;
  }
  if (!business.data) {
    return <Alert tone="info">This seller has not submitted business verification yet.</Alert>;
  }

  const review = business.data;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 rounded-md border border-border/70 p-3 text-sm sm:grid-cols-2">
        <p>
          Legal name: <strong>{review.legalName ?? '—'}</strong>
        </p>
        <p>
          Registration number: <strong>{review.registrationNumber ?? '—'}</strong>
        </p>
      </div>
      {review.previewUrl && (
        <figure className="overflow-hidden rounded-md border border-border/70">
          <img
            src={review.previewUrl}
            alt="Business registration document"
            className="max-h-96 w-full object-contain"
          />
        </figure>
      )}
      <p className="text-xs text-muted-foreground">
        Images use short-lived private URLs and are not stored in the browser cache by TrustLens.
      </p>
    </div>
  );
}
