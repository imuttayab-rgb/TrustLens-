'use client';

import { useApiForm } from '@/lib/forms/use-api-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Alert, Button, Field, fieldAria } from '@trustlens/ui';
import { appealSchema, type AppealInput } from '@trustlens/validation';
import { useForm } from 'react-hook-form';
import { useSubmitAppeal, type AppealReasonCategory } from '../hooks/use-appeals';

/**
 * The category routes the appeal; the text explains it. Free text alone makes
 * triage impossible, and a category alone is not something a reviewer can act
 * on - hence both, with the labels phrased as the seller would say them.
 */
const CATEGORY_LABELS: Record<AppealReasonCategory, string> = {
  IDENTITY_INCORRECT: 'My ID check was judged wrongly',
  PHONE_INCORRECT: 'My phone number was judged wrongly',
  LISTING_MISJUDGED: 'One of my listings was judged wrongly',
  DEVICE_INCORRECT: 'The device or network finding is wrong',
  OTHER: 'Something else',
};

export function AppealForm({
  sellerId,
  trustScoreId,
  onDone,
}: {
  sellerId: string;
  trustScoreId: string;
  onDone?: () => void;
}) {
  const submitAppeal = useSubmitAppeal();

  const {
    register,
    handleSubmit,
    setError,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<AppealInput>({
    resolver: zodResolver(appealSchema),
    defaultValues: { trustScoreId, reasonCategory: 'IDENTITY_INCORRECT', reason: '' },
  });

  const { submit, formError } = useApiForm<AppealInput>(setError);
  const reason = watch('reason') ?? '';

  const onSubmit = handleSubmit(async (values) => {
    const ok = await submit(async () => {
      await submitAppeal.mutateAsync({
        sellerId,
        trustScoreId: values.trustScoreId,
        reasonCategory: values.reasonCategory,
        reason: values.reason,
      });
    });
    if (ok) onDone?.();
  });

  return (
    <form onSubmit={(event) => void onSubmit(event)} className="space-y-4" noValidate>
      {/* The appeal is against one computation, not "my score". Hidden rather
          than shown: the seller has no use for a uuid, but the reviewer needs
          to know which breakdown is being disputed. */}
      <input type="hidden" {...register('trustScoreId')} />

      <Field
        htmlFor="reasonCategory"
        label="What are you appealing?"
        required
        error={errors.reasonCategory?.message}
      >
        <select
          {...fieldAria('reasonCategory', errors.reasonCategory?.message)}
          className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          {...register('reasonCategory')}
        >
          {(Object.keys(CATEGORY_LABELS) as AppealReasonCategory[]).map((key) => (
            <option key={key} value={key}>
              {CATEGORY_LABELS[key]}
            </option>
          ))}
        </select>
      </Field>

      <Field
        htmlFor="reason"
        label="What is wrong, and why?"
        required
        error={errors.reason?.message}
        hint="A reviewer reads this. Say what the system got wrong and what the truth is."
      >
        <textarea
          {...fieldAria('reason', errors.reason?.message)}
          rows={5}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          placeholder="My CNIC photo was clear and the document is genuine and unexpired."
          {...register('reason')}
        />
      </Field>

      <p className="text-xs tabular-nums text-muted-foreground">
        {reason.trim().length} / 20 characters minimum
      </p>

      {formError && (
        <Alert tone="error" requestId={formError.requestId}>
          {formError.message}
        </Alert>
      )}

      <div className="flex gap-2">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Submitting…' : 'Submit appeal'}
        </Button>
        {onDone && (
          <Button type="button" variant="outline" onClick={onDone}>
            Cancel
          </Button>
        )}
      </div>

      <p className="text-xs text-muted-foreground">
        You can have one open appeal at a time, and up to three every 30 days.
      </p>
    </form>
  );
}
