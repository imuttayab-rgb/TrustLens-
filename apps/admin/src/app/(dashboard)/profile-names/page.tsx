/** Next.js route/layout composition for (dashboard)/profile-names: page. */
'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import Image from 'next/image';
import { Alert, Button, Spinner } from '@trustlens/ui';
import { profileRequest } from '@/lib/profile-api';
interface Review {
  id: string;
  userId: string;
  requestedName: string;
  extractedName: string | null;
  ocrEngine: string | null;
  note: string;
  documentUrl: string | null;
  createdAt: string;
}
function ReviewCard({ review }: { review: Review }) {
  const [note, setNote] = useState('');
  const qc = useQueryClient();
  const decide = useMutation({
    mutationFn: (approve: boolean) =>
      profileRequest(`/admin/profile-name-reviews/${review.id}`, {
        method: 'POST',
        body: JSON.stringify({ approve, note }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'profile-names'] }),
  });
  return (
    <article className="space-y-4 rounded-xl border border-border bg-card p-5">
      <h2 className="text-lg font-semibold">Name correction</h2>
      <dl className="grid gap-2 text-sm">
        <div>
          Requested: <strong>{review.requestedName}</strong>
        </div>
        <div>
          OCR read: {review.extractedName ?? 'Unavailable'} ({review.ocrEngine ?? 'unknown engine'})
        </div>
        <div>Owner note: {review.note || 'None'}</div>
      </dl>
      {review.documentUrl ? (
        <a
          href={review.documentUrl}
          target="_blank"
          rel="noreferrer"
          className="relative block h-56 max-w-lg"
        >
          <Image
            src={review.documentUrl}
            fill
            unoptimized
            sizes="500px"
            alt="Private identity document for authorized name review"
            className="object-contain"
          />
        </a>
      ) : (
        <Alert tone="warning">
          The private evidence has expired. Ask for a new ID verification; do not approve without
          evidence.
        </Alert>
      )}
      <p className="text-xs text-muted-foreground">
        Compare the requested name against the document. Spelling/transliteration needs human
        review. This approval does not override identity verification or approve a profile photo.
      </p>
      <label className="block text-sm">
        Decision note (shown to user)
        <textarea
          rows={2}
          minLength={10}
          maxLength={1000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="mt-1 w-full rounded border border-input bg-background p-2"
        />
      </label>
      {decide.error && <Alert tone="error">{decide.error.message}</Alert>}
      <div className="flex gap-3">
        <Button
          disabled={!review.documentUrl || note.trim().length < 10 || decide.isPending}
          onClick={() => decide.mutate(true)}
        >
          Approve name
        </Button>
        <Button
          variant="outline"
          disabled={note.trim().length < 10 || decide.isPending}
          onClick={() => decide.mutate(false)}
        >
          Request correction
        </Button>
      </div>
    </article>
  );
}
export default function ProfileNameReviews() {
  const { data, isPending, error, refetch } = useQuery<Review[]>({
    queryKey: ['admin', 'profile-names'],
    queryFn: () => profileRequest('/admin/profile-name-reviews'),
    refetchInterval: 30_000,
    retry: 1,
  });
  return (
    <main className="space-y-5 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Profile name reviews</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Private ID-name corrections. Decisions are audited; you cannot approve your own name.
          </p>
        </div>
        <Button variant="outline" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>
      {isPending ? (
        <Spinner label="Loading reviews" />
      ) : error ? (
        <Alert tone="error">{error.message}</Alert>
      ) : !data?.length ? (
        <p className="py-12 text-muted-foreground">No pending name reviews.</p>
      ) : (
        data.map((r) => <ReviewCard key={r.id} review={r} />)
      )}
    </main>
  );
}
