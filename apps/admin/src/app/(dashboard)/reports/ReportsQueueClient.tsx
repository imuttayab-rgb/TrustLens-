'use client';

import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Card, CardContent, Spinner } from '@trustlens/ui';
import { formatDateTime } from '@trustlens/utils';
import { useState } from 'react';
import {
  useReportQueue,
  useResolveReport,
  type AdminReport,
  type ReportStatus,
} from '@/features/reports';

const STATUS_TABS: { value: ReportStatus | undefined; label: string }[] = [
  { value: undefined, label: 'All' },
  { value: 'OPEN', label: 'Open' },
  { value: 'UNDER_REVIEW', label: 'Under review' },
  { value: 'RESOLVED', label: 'Resolved' },
  { value: 'DISMISSED', label: 'Dismissed' },
];

export function ReportsQueueClient() {
  const [statusFilter, setStatusFilter] = useState<ReportStatus | undefined>(undefined);
  const { data, isPending, error } = useReportQueue(statusFilter);

  if (isPending) {
    return (
      <div className="flex justify-center p-12">
        <Spinner label="Loading reports" />
      </div>
    );
  }
  if (error) {
    return (
      <main className="p-8">
        <Alert tone="error">Unable to load the reports queue.</Alert>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6 sm:p-8">
      <div>
        <h1 className="text-2xl font-bold">Reports</h1>
        <p className="mt-1 text-muted-foreground">
          Every listing, seller, or message a user has flagged. Separate from the identity-review
          and appeal queues - this is content/conduct moderation, not a score decision.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUS_TABS.map((tab) => (
          <Button
            key={tab.label}
            size="sm"
            variant={statusFilter === tab.value ? 'default' : 'outline'}
            onClick={() => setStatusFilter(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {data.items.length === 0 ? (
        <Alert tone="success">Nothing here right now.</Alert>
      ) : (
        <div className="space-y-3">
          {data.items.map((report) => (
            <ReportRow key={report.id} report={report} />
          ))}
        </div>
      )}
    </main>
  );
}

function ReportRow({ report }: { report: AdminReport }) {
  const resolve = useResolveReport();
  const [note, setNote] = useState('');
  const [failure, setFailure] = useState<string | null>(null);
  const isOpen = report.status === 'OPEN' || report.status === 'UNDER_REVIEW';

  function submit(status: 'RESOLVED' | 'DISMISSED') {
    setFailure(null);
    resolve.mutate(
      { reportId: report.id, status, resolutionNote: note },
      { onError: (e) => setFailure(toApiError(e).message) },
    );
  }

  return (
    <Card>
      <CardContent className="space-y-3 pt-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="font-medium">
              {report.targetType} · {report.category.replace(/_/g, ' ').toLowerCase()}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              target {report.targetId.slice(0, 8)}… · reported {formatDateTime(report.createdAt)}
            </p>
          </div>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
            {report.status.replace(/_/g, ' ').toLowerCase()}
          </span>
        </div>

        <p className="text-sm">{report.description}</p>

        {report.resolutionNote && (
          <div className="rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Resolution: </span>
            {report.resolutionNote}
          </div>
        )}

        {isOpen && (
          <div className="space-y-2 border-t border-border/70 pt-3">
            <label htmlFor={`note-${report.id}`} className="block text-sm font-medium">
              Resolution note
            </label>
            <textarea
              id={`note-${report.id}`}
              rows={2}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="What did you find, and what did you do about it?"
            />
            {failure && <Alert tone="error">{failure}</Alert>}
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={!note.trim() || resolve.isPending}
                onClick={() => submit('RESOLVED')}
              >
                Mark resolved
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!note.trim() || resolve.isPending}
                onClick={() => submit('DISMISSED')}
              >
                Dismiss
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
