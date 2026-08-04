'use client';

import { ReviewQueue } from '@/features/review';

export default function ReviewQueuePage() {
  return (
    <main className="mx-auto max-w-3xl p-6 sm:p-8">
      <h1 className="text-2xl font-bold">Review queue</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Ordered by priority, then age. Most cases are opened by the system — a borderline face
        match, an unreadable document, a device behind several accounts — because the pipeline
        deliberately declines to decide rather than penalising someone it is unsure about.
      </p>

      <div className="mt-8">
        <ReviewQueue />
      </div>
    </main>
  );
}
