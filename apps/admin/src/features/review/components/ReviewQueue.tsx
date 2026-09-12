'use client';

import { MIN_DECISION_NOTE_CHARS } from '../constants';
import {
  useClaimCase,
  useDecideCase,
  useIdentityReview,
  useReviewQueue,
  type ReviewCase,
} from '../hooks/use-review-queue';
import { IdentityEvidence } from './IdentityEvidence';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Card, CardContent, Spinner, cn } from '@trustlens/ui';
import { formatDateTime } from '@trustlens/utils';
import { ShieldAlert, ShieldCheck, TriangleAlert, UserSearch } from 'lucide-react';
import { useState } from 'react';

const CASE_ICON = {
  IDENTITY_REVIEW: UserSearch,
  FRAUD_FLAG: ShieldAlert,
  APPEAL: TriangleAlert,
  DEVICE_CLUSTER: ShieldAlert,
} as const;

/** Lower number = more urgent, matching the queue's own ordering. */
function priorityTone(priority: number) {
  if (priority <= 2) return 'text-risk-high bg-risk-high-bg';
  if (priority <= 5) return 'text-risk-medium bg-risk-medium-bg';
  return 'text-risk-unknown bg-risk-unknown-bg';
}

export function ReviewQueue() {
  const { data: cases, isPending, error } = useReviewQueue();
  const [openId, setOpenId] = useState<string | null>(null);

  if (isPending) {
    return (
      <div className="flex min-h-[40dvh] items-center justify-center">
        <Spinner label="Loading the review queue" />
      </div>
    );
  }

  if (error) {
    const apiError = toApiError(error);
    return (
      <Alert tone="error" title="The queue could not be loaded" requestId={apiError.requestId}>
        {apiError.message}
      </Alert>
    );
  }

  const open = (cases ?? []).filter((c) => c.status === 'QUEUED' || c.status === 'ASSIGNED');
  const closed = (cases ?? []).filter((c) => c.status !== 'QUEUED' && c.status !== 'ASSIGNED');

  return (
    <div className="space-y-8">
      <section>
        <h2 className="text-sm font-semibold">
          Open <span className="font-normal text-muted-foreground">({open.length})</span>
        </h2>
        {open.length === 0 ? (
          <Alert tone="success" className="mt-3">
            Nothing waiting. Cases appear here when the pipeline declines to decide on its own.
          </Alert>
        ) : (
          <ul className="mt-3 space-y-3">
            {open.map((item) => (
              <li key={item.id}>
                <CaseRow
                  item={item}
                  expanded={openId === item.id}
                  onToggle={() => setOpenId(openId === item.id ? null : item.id)}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      {closed.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold">
            Decided <span className="font-normal text-muted-foreground">({closed.length})</span>
          </h2>
          <ul className="mt-3 space-y-2">
            {closed.map((item) => (
              <li
                key={item.id}
                className="flex items-start gap-3 rounded-lg border border-border/70 bg-card/40 p-3 text-sm"
              >
                <ShieldCheck
                  className={cn(
                    'mt-0.5 h-4 w-4 shrink-0',
                    item.status === 'APPROVED' ? 'text-risk-low' : 'text-risk-high',
                  )}
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <p className="font-medium">
                    {item.case_type.replace(/_/g, ' ').toLowerCase()} · {item.status.toLowerCase()}
                  </p>
                  {item.decision_note && (
                    <p className="mt-0.5 text-muted-foreground">{item.decision_note}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function CaseRow({
  item,
  expanded,
  onToggle,
}: {
  item: ReviewCase;
  expanded: boolean;
  onToggle: () => void;
}) {
  const claim = useClaimCase();
  const decide = useDecideCase();
  const identity = useIdentityReview(
    item.seller_id,
    expanded && item.case_type === 'IDENTITY_REVIEW',
  );
  const [note, setNote] = useState('');
  const [failure, setFailure] = useState<string | null>(null);

  const Icon = CASE_ICON[item.case_type] ?? UserSearch;
  const claimed = item.status === 'ASSIGNED';
  const noteTooShort = note.trim().length < MIN_DECISION_NOTE_CHARS;

  function submit(approve: boolean) {
    setFailure(null);
    decide.mutate(
      { caseId: item.id, approve, note },
      {
        onError: (err) => setFailure(toApiError(err).message),
        onSuccess: () => setNote(''),
      },
    );
  }

  return (
    <Card>
      <CardContent className="pt-5">
        <div className="flex items-start gap-3">
          <span className={cn('mt-0.5 rounded-full p-1.5', priorityTone(item.priority))}>
            <Icon className="h-4 w-4" aria-hidden="true" />
          </span>

          <div className="min-w-0 flex-1">
            <p className="font-medium">{item.trigger_reason ?? 'Manual review'}</p>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {item.case_type.replace(/_/g, ' ').toLowerCase()} · priority {item.priority} ·{' '}
              {formatDateTime(item.created_at)}
            </p>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              seller {item.seller_id.slice(0, 8)}…
            </p>
          </div>

          <Button variant="outline" size="sm" onClick={onToggle}>
            {expanded ? 'Close' : 'Open'}
          </Button>
        </div>

        {expanded && (
          <div className="mt-5 space-y-4 border-t border-border/70 pt-5">
            {!claimed ? (
              <>
                <Alert tone="info">
                  Claim this case before deciding it. Claiming is what stops two reviewers reaching
                  different conclusions on the same evidence.
                </Alert>
                <Button
                  disabled={claim.isPending}
                  onClick={() =>
                    claim.mutate(item.id, { onError: (e) => setFailure(toApiError(e).message) })
                  }
                >
                  {claim.isPending ? 'Claiming…' : 'Claim this case'}
                </Button>
              </>
            ) : (
              <>
                {item.case_type === 'IDENTITY_REVIEW' && <IdentityEvidence identity={identity} />}

                <div>
                  <label htmlFor={`note-${item.id}`} className="block text-sm font-medium">
                    Why this decision?
                  </label>
                  <p className="mb-2 mt-1 text-xs text-muted-foreground">
                    Recorded against your account and shown to the seller if they appeal. At least{' '}
                    {MIN_DECISION_NOTE_CHARS} characters.
                  </p>
                  <textarea
                    id={`note-${item.id}`}
                    rows={3}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </div>

                {failure && <Alert tone="error">{failure}</Alert>}

                <div className="flex flex-wrap gap-2">
                  <Button disabled={noteTooShort || decide.isPending} onClick={() => submit(true)}>
                    {decide.isPending ? 'Saving…' : 'Approve'}
                  </Button>
                  <Button
                    variant="destructive"
                    disabled={noteTooShort || decide.isPending}
                    onClick={() => submit(false)}
                  >
                    Reject
                  </Button>
                </div>
              </>
            )}

            {failure && !claimed && <Alert tone="error">{failure}</Alert>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
