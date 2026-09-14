'use client';

import { useMyReports, type ReportCategory, type ReportTargetType } from '@/features/moderation';
import { Alert, Spinner } from '@trustlens/ui';
import { formatDateTime } from '@trustlens/utils';

const CATEGORY_LABELS: Record<ReportCategory, string> = {
  SCAM_OR_FRAUD: 'Scam or fraud',
  PROHIBITED_ITEM: 'Prohibited item',
  HARASSMENT: 'Harassment or abuse',
  MISLEADING_LISTING: 'Misleading listing',
  OTHER: 'Something else',
};

const TARGET_LABELS: Record<ReportTargetType, string> = {
  LISTING: 'Listing',
  SELLER: 'Seller',
  MESSAGE: 'Message',
  TRANSACTION: 'Transaction dispute',
  MEETUP: 'SafeMeet incident',
  OTHER: 'Other',
};

const STATUS_TONE: Record<string, 'info' | 'success' | 'warning'> = {
  OPEN: 'info',
  UNDER_REVIEW: 'info',
  RESOLVED: 'success',
  DISMISSED: 'warning',
};

export default function MyReportsPage() {
  const { data: reports, isPending, isError } = useMyReports();

  return (
    <div>
      <h1 className="text-2xl font-bold">Your reports</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Reports you&apos;ve filed against a listing, seller, or message. Staff review these -
        reported items aren&apos;t removed automatically.
      </p>

      <div className="mt-8">
        {isPending ? (
          <div className="flex justify-center py-16">
            <Spinner label="Loading your reports" />
          </div>
        ) : isError ? (
          <Alert tone="error" title="Could not load your reports">
            Try again in a moment.
          </Alert>
        ) : reports.length === 0 ? (
          <Alert tone="info" title="No reports yet">
            You can report a listing or seller from its page.
          </Alert>
        ) : (
          <ul className="space-y-3">
            {reports.map((report) => (
              <li key={report.id} className="rounded-lg border border-border p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium">
                    {TARGET_LABELS[report.targetType]} · {CATEGORY_LABELS[report.category]}
                  </p>
                  <span
                    className={
                      'rounded-full px-2 py-0.5 text-xs font-medium ' +
                      (STATUS_TONE[report.status] === 'success'
                        ? 'bg-risk-low-bg text-risk-low'
                        : STATUS_TONE[report.status] === 'warning'
                          ? 'bg-risk-medium-bg text-risk-medium'
                          : 'bg-risk-unknown-bg text-risk-unknown')
                    }
                  >
                    {report.status.replace(/_/g, ' ').toLowerCase()}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{report.description}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  Filed {formatDateTime(report.createdAt)}
                </p>
                {report.resolutionNote && (
                  <div className="mt-2 rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">Staff note: </span>
                    {report.resolutionNote}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
