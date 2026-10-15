/** Reusable UI rendering and interaction component: AppealList. */
'use client';

import { Alert, Button, Card, CardContent, CardHeader, CardTitle, Spinner } from '@trustlens/ui';
import { formatDateTime } from '@trustlens/utils';
import { useState } from 'react';
import {
  isOpen,
  useMyAppeals,
  useReplyToAppeal,
  useWithdrawAppeal,
  type Appeal,
  type AppealStatus,
} from '../hooks/use-appeals';

/** Plain words, not enum names. A seller should not have to decode NEEDS_INFO. */
const STATUS_LABELS: Record<AppealStatus, string> = {
  OPEN: 'Waiting for a reviewer',
  UNDER_REVIEW: 'Being reviewed',
  NEEDS_INFO: 'More information needed',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  WITHDRAWN: 'Withdrawn',
};

const STATUS_TONE: Record<AppealStatus, string> = {
  OPEN: 'text-muted-foreground',
  UNDER_REVIEW: 'text-muted-foreground',
  NEEDS_INFO: 'text-risk-medium',
  APPROVED: 'text-risk-low',
  REJECTED: 'text-risk-high',
  WITHDRAWN: 'text-muted-foreground',
};

function AppealCard({ appeal }: { appeal: Appeal }) {
  const withdraw = useWithdrawAppeal();
  const reply = useReplyToAppeal();
  const [draft, setDraft] = useState('');
  const open = isOpen(appeal);

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="text-base">{appeal.reason}</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            Submitted {formatDateTime(appeal.submittedAt)}
          </p>
        </div>
        <span className={`shrink-0 text-sm font-medium ${STATUS_TONE[appeal.status]}`}>
          {STATUS_LABELS[appeal.status]}
        </span>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* The decision is the whole point of appealing, so it is shown in
            full rather than summarised. */}
        {appeal.resolutionNote && (
          <Alert tone={appeal.status === 'APPROVED' ? 'success' : 'info'}>
            <span className="font-medium">Reviewer&rsquo;s decision: </span>
            {appeal.resolutionNote}
          </Alert>
        )}

        {appeal.messages.length > 0 && (
          <ol className="space-y-3 border-l pl-4">
            {appeal.messages.map((message) => (
              <li key={message.id}>
                <p className="text-xs text-muted-foreground">
                  {message.senderRole === 'SELLER' ? 'You' : 'Reviewer'} ·{' '}
                  {formatDateTime(message.createdAt)}
                </p>
                <p className="text-sm">{message.body}</p>
              </li>
            ))}
          </ol>
        )}

        {open && (
          <div className="space-y-2">
            <textarea
              aria-label="Reply to the reviewer"
              rows={2}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Add anything that helps the reviewer decide."
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={!draft.trim() || reply.isPending}
                onClick={() => {
                  void reply
                    .mutateAsync({ appealId: appeal.id, body: draft.trim() })
                    .then(() => setDraft(''))
                    // The thread is not the place to lose a message silently;
                    // the list refetches and the draft stays put on failure.
                    .catch(() => undefined);
                }}
              >
                {reply.isPending ? 'Sending…' : 'Send reply'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={withdraw.isPending}
                onClick={() => void withdraw.mutateAsync(appeal.id).catch(() => undefined)}
              >
                {withdraw.isPending ? 'Withdrawing…' : 'Withdraw'}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Withdrawing frees your one open appeal, so you can submit a better one.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function AppealList() {
  const { data: appeals = [], isPending } = useMyAppeals();

  if (isPending) {
    return (
      <div className="flex min-h-[20dvh] items-center justify-center">
        <Spinner label="Loading your appeals" />
      </div>
    );
  }

  if (appeals.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        You have not appealed anything. If a check on your score looks wrong, you can dispute it
        from your score breakdown.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {appeals.map((appeal) => (
        <AppealCard key={appeal.id} appeal={appeal} />
      ))}
    </div>
  );
}
