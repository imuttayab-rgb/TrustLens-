/** Reusable UI rendering and interaction component: AppealQueue. */
'use client';

import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Card, CardContent, Spinner, cn } from '@trustlens/ui';
import { formatDateTime } from '@trustlens/utils';
import { useState } from 'react';
import {
  useAppealMessage,
  useAppealQueue,
  useClaimAppeal,
  useResolveAppeal,
  type Appeal,
  type AppealDecision,
} from '../hooks/use-appeal-queue';

/** Matches the backend's MIN_REASON_CHARS: the seller reads this note. */
const MIN_NOTE_CHARS = 20;

const CATEGORY_LABELS: Record<string, string> = {
  IDENTITY_INCORRECT: 'Identity check',
  PHONE_INCORRECT: 'Phone check',
  LISTING_MISJUDGED: 'Listing analysis',
  DEVICE_INCORRECT: 'Device / network',
  OTHER: 'Other',
};

const STATUS_TONE: Record<string, string> = {
  OPEN: 'text-risk-medium bg-risk-medium-bg',
  UNDER_REVIEW: 'text-risk-unknown bg-risk-unknown-bg',
  NEEDS_INFO: 'text-risk-medium bg-risk-medium-bg',
  APPROVED: 'text-risk-low bg-risk-low-bg',
  REJECTED: 'text-risk-high bg-risk-high-bg',
  WITHDRAWN: 'text-risk-unknown bg-risk-unknown-bg',
};

function AppealRow({
  appeal,
  expanded,
  onToggle,
}: {
  appeal: Appeal;
  expanded: boolean;
  onToggle: () => void;
}) {
  const claim = useClaimAppeal();
  const resolve = useResolveAppeal();
  const message = useAppealMessage();

  const [note, setNote] = useState('');
  const [decision, setDecision] = useState<AppealDecision>('RECOMPUTE');
  const [overrideScore, setOverrideScore] = useState('');
  const [internalNote, setInternalNote] = useState('');
  // `?: T | undefined` rather than `?: T`: the tsconfig sets
  // exactOptionalPropertyTypes, and requestId is copied straight off ApiError
  // where it may be present-but-undefined.
  const [failure, setFailure] = useState<{
    message: string;
    requestId?: string | undefined;
  } | null>(null);

  const noteTooShort = note.trim().length < MIN_NOTE_CHARS;
  const busy = resolve.isPending || claim.isPending;

  function report(error: unknown) {
    const parsed = toApiError(error);
    setFailure({ message: parsed.message, requestId: parsed.requestId });
  }

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <button
          type="button"
          onClick={onToggle}
          className="flex w-full items-start justify-between gap-4 text-left"
        >
          <div className="min-w-0">
            <p className="text-sm font-medium">
              {CATEGORY_LABELS[appeal.reasonCategory] ?? appeal.reasonCategory}
            </p>
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{appeal.reason}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Submitted {formatDateTime(appeal.submittedAt)}
              {appeal.assignedTo && ' · claimed'}
            </p>
          </div>
          <span
            className={cn(
              'shrink-0 rounded-full px-2 py-0.5 text-xs font-medium',
              STATUS_TONE[appeal.status],
            )}
          >
            {appeal.status.replace('_', ' ').toLowerCase()}
          </span>
        </button>

        {expanded && (
          <div className="space-y-4 border-t pt-4">
            {appeal.messages.length > 0 && (
              <ol className="space-y-2">
                {appeal.messages.map((m) => (
                  <li key={m.id} className={cn('text-sm', m.isInternal && 'opacity-80')}>
                    <span className="text-xs text-muted-foreground">
                      {m.senderRole.toLowerCase()}
                      {m.isInternal && ' · internal'} · {formatDateTime(m.createdAt)}
                    </span>
                    <p>{m.body}</p>
                  </li>
                ))}
              </ol>
            )}

            {appeal.status === 'OPEN' && (
              <Button
                size="sm"
                disabled={busy}
                onClick={() => {
                  setFailure(null);
                  void claim.mutateAsync(appeal.id).catch(report);
                }}
              >
                {claim.isPending ? 'Claiming…' : 'Claim this appeal'}
              </Button>
            )}

            {(appeal.status === 'UNDER_REVIEW' || appeal.status === 'NEEDS_INFO') && (
              <div className="space-y-3">
                <div className="space-y-2">
                  <label className="text-sm font-medium" htmlFor={`note-${appeal.id}`}>
                    Decision note
                  </label>
                  <textarea
                    id={`note-${appeal.id}`}
                    rows={3}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="The seller reads this. Say what you checked and what you concluded."
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  />
                  <p className="text-xs tabular-nums text-muted-foreground">
                    {note.trim().length} / {MIN_NOTE_CHARS} characters minimum
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <select
                    aria-label="Decision"
                    value={decision}
                    onChange={(e) => setDecision(e.target.value as AppealDecision)}
                    className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                  >
                    <option value="RECOMPUTE">Approve — recompute from corrected evidence</option>
                    <option value="OVERRIDE">Approve — override the score (admin only)</option>
                    <option value="REJECT">Reject</option>
                  </select>

                  {decision === 'OVERRIDE' && (
                    <input
                      aria-label="Override score"
                      inputMode="numeric"
                      value={overrideScore}
                      onChange={(e) => setOverrideScore(e.target.value)}
                      placeholder="0-100"
                      className="h-9 w-24 rounded-md border border-input bg-background px-2 text-sm"
                    />
                  )}

                  <Button
                    size="sm"
                    disabled={busy || noteTooShort}
                    onClick={() => {
                      setFailure(null);
                      const parsed = Number(overrideScore);
                      void resolve
                        .mutateAsync({
                          appealId: appeal.id,
                          decision,
                          note: note.trim(),
                          ...(decision === 'OVERRIDE' && Number.isFinite(parsed)
                            ? { overrideScore: parsed }
                            : {}),
                        })
                        .then(() => setNote(''))
                        .catch(report);
                    }}
                  >
                    {resolve.isPending ? 'Recording…' : 'Record decision'}
                  </Button>
                </div>

                {/* Overriding writes a number a human chose rather than one the
                    signals produced, so it is worth saying out loud. */}
                {decision === 'OVERRIDE' && (
                  <Alert tone="warning">
                    An override replaces the computed score for 90 days and is admin-only. Prefer
                    recomputing unless the evidence genuinely cannot be corrected.
                  </Alert>
                )}

                <div className="space-y-2 border-t pt-3">
                  <label className="text-sm font-medium" htmlFor={`internal-${appeal.id}`}>
                    Internal note{' '}
                    <span className="font-normal text-muted-foreground">
                      — never shown to the seller
                    </span>
                  </label>
                  <div className="flex gap-2">
                    <input
                      id={`internal-${appeal.id}`}
                      value={internalNote}
                      onChange={(e) => setInternalNote(e.target.value)}
                      placeholder="Context for the next reviewer."
                      className="h-9 flex-1 rounded-md border border-input bg-background px-2 text-sm"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!internalNote.trim() || message.isPending}
                      onClick={() => {
                        setFailure(null);
                        void message
                          .mutateAsync({
                            appealId: appeal.id,
                            body: internalNote.trim(),
                            isInternal: true,
                          })
                          .then(() => setInternalNote(''))
                          .catch(report);
                      }}
                    >
                      Add
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {appeal.resolutionNote && (
              <Alert tone="info" title={`Decision: ${appeal.decision}`}>
                {appeal.resolutionNote}
              </Alert>
            )}

            {failure && (
              <Alert tone="error" requestId={failure.requestId}>
                {failure.message}
              </Alert>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function AppealQueue() {
  const { data: appeals, isPending, error } = useAppealQueue();
  const [openId, setOpenId] = useState<string | null>(null);

  if (isPending) {
    return (
      <div className="flex min-h-[40dvh] items-center justify-center">
        <Spinner label="Loading the appeal queue" />
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

  const items = appeals ?? [];

  if (items.length === 0) {
    return (
      <Alert tone="success">
        No appeals waiting. Sellers appear here when they dispute a check behind their score.
      </Alert>
    );
  }

  return (
    <ul className="space-y-3">
      {items.map((appeal) => (
        <li key={appeal.id}>
          <AppealRow
            appeal={appeal}
            expanded={openId === appeal.id}
            onToggle={() => setOpenId(openId === appeal.id ? null : appeal.id)}
          />
        </li>
      ))}
    </ul>
  );
}
