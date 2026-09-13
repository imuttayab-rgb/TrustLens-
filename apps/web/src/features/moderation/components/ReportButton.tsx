'use client';

import { useSession } from '@/lib/auth/use-session';
import { Alert, Button, Field } from '@trustlens/ui';
import { Flag } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';
import { toApiError } from '@trustlens/api-client';
import {
  useCreateReport,
  type ReportCategory,
  type ReportTargetType,
} from '../hooks/use-moderation';

const CATEGORY_LABELS: Record<ReportCategory, string> = {
  SCAM_OR_FRAUD: 'Scam or fraud',
  PROHIBITED_ITEM: 'Prohibited item',
  HARASSMENT: 'Harassment or abuse',
  MISLEADING_LISTING: 'Misleading listing',
  OTHER: 'Something else',
};

const MIN_DESCRIPTION_CHARS = 10;

/**
 * Report a listing or seller. Idempotent-ish only in spirit - staff review
 * every submission, so this deliberately doesn't dedupe repeated reports the
 * way a favourite or a block does.
 */
export function ReportButton({
  targetType,
  targetId,
  label = 'Report',
}: {
  targetType: ReportTargetType;
  targetId: string;
  label?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<ReportCategory>('SCAM_OR_FRAUD');
  const [description, setDescription] = useState('');
  const [failure, setFailure] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const createReport = useCreateReport();

  function startReport() {
    if (!session) {
      router.push(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    setOpen(true);
  }

  function submit() {
    setFailure(null);
    createReport.mutate(
      { targetType, targetId, category, description },
      {
        onSuccess: () => setDone(true),
        onError: (error) => setFailure(toApiError(error).message),
      },
    );
  }

  if (done) {
    return (
      <Alert tone="success" className="text-sm">
        Report received. Staff review submissions - you don&apos;t need to do anything else.
      </Alert>
    );
  }

  if (!open) {
    return (
      <Button variant="outline" size="sm" onClick={startReport}>
        <Flag className="h-4 w-4" aria-hidden="true" />
        {label}
      </Button>
    );
  }

  const trimmed = description.trim();
  const canSubmit = trimmed.length >= MIN_DESCRIPTION_CHARS;

  return (
    <div className="space-y-3 rounded-lg border border-border p-4">
      <Field htmlFor="report-category" label="What's wrong?">
        <select
          id="report-category"
          value={category}
          onChange={(event) => setCategory(event.target.value as ReportCategory)}
          className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {(Object.keys(CATEGORY_LABELS) as ReportCategory[]).map((key) => (
            <option key={key} value={key}>
              {CATEGORY_LABELS[key]}
            </option>
          ))}
        </select>
      </Field>

      <Field
        htmlFor="report-description"
        label="Describe what happened"
        hint={`${trimmed.length} / ${MIN_DESCRIPTION_CHARS} characters minimum`}
      >
        <textarea
          id="report-description"
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </Field>

      {failure && <Alert tone="error">{failure}</Alert>}

      <div className="flex gap-2">
        <Button size="sm" disabled={!canSubmit || createReport.isPending} onClick={submit}>
          {createReport.isPending ? 'Submitting…' : 'Submit report'}
        </Button>
        <Button size="sm" variant="outline" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
