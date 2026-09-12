'use client';

import type { useIdentityReview } from '../hooks/use-identity-review';
import { Alert, Spinner } from '@trustlens/ui';

/**
 * CNIC + selfie images and the face-match verdict, via the short-lived
 * signed URLs `GET /admin/sellers/{id}/identity-review` returns. Shared
 * between the in-flight review queue and the seller-detail page so the
 * evidence viewer is reachable without first claiming a review case.
 */
export function IdentityEvidence({ identity }: { identity: ReturnType<typeof useIdentityReview> }) {
  if (identity.isPending) return <Spinner label="Loading identity evidence" />;
  if (identity.error) {
    return <Alert tone="error">Identity evidence could not be loaded.</Alert>;
  }
  if (!identity.data) {
    return <Alert tone="info">This seller has not submitted identity verification yet.</Alert>;
  }

  const review = identity.data;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {review.documents.map((document) => (
          <figure
            key={document.documentType}
            className="overflow-hidden rounded-md border border-border/70"
          >
            <img
              src={document.previewUrl}
              alt={document.documentType.replace('_', ' ').toLowerCase()}
              className="aspect-video w-full object-cover"
            />
            <figcaption className="space-y-1 p-3 text-xs">
              <p className="font-medium">{document.documentType.replace('_', ' ')}</p>
              <p className="text-muted-foreground">Status: {document.status}</p>
              {document.extractedName && (
                <p className="text-muted-foreground">Name: {document.extractedName}</p>
              )}
              {document.ocrConfidence != null && (
                <p className="text-muted-foreground">
                  OCR confidence: {(document.ocrConfidence * 100).toFixed(0)}%
                </p>
              )}
            </figcaption>
          </figure>
        ))}
      </div>
      <div className="grid gap-3 rounded-md border border-border/70 p-3 text-sm sm:grid-cols-3">
        <p>
          Decision: <strong>{review.decision}</strong>
        </p>
        <p>
          Face similarity: <strong>{review.faceSimilarity?.toFixed(3) ?? '—'}</strong>
        </p>
        <p>
          Threshold: <strong>{review.thresholdUsed?.toFixed(3) ?? '—'}</strong>
        </p>
      </div>
      <p className="text-xs text-muted-foreground">
        Images use short-lived private URLs and are not stored in the browser cache by TrustLens.
      </p>
    </div>
  );
}
