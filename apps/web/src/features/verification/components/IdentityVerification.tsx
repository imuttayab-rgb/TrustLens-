'use client';

import { api } from '@/lib/api/client';
import type { FormError } from '@/lib/forms/use-api-form';
import { qk } from '@/lib/api/query-keys';
import { uploadFile } from '@/lib/upload';
import { useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Card, CardContent, Spinner } from '@trustlens/ui';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useJobStatus } from '../hooks/use-job-status';
import { CaptureTips, ImageCapture } from './ImageCapture';

type Slot = 'cnicFront' | 'cnicBack' | 'selfie';

const SLOTS: {
  key: Slot;
  purpose: string;
  label: string;
  hint: string;
  facing: 'environment' | 'user';
}[] = [
  {
    key: 'cnicFront',
    purpose: 'CNIC_FRONT',
    label: 'CNIC — front',
    hint: 'The side with your photo and CNIC number',
    facing: 'environment',
  },
  {
    key: 'cnicBack',
    purpose: 'CNIC_BACK',
    label: 'CNIC — back',
    hint: 'The side with your address and expiry date',
    facing: 'environment',
  },
  {
    key: 'selfie',
    purpose: 'SELFIE',
    label: 'Selfie',
    hint: 'Face the camera in good light, no sunglasses or hat',
    facing: 'user',
  },
];

export function IdentityVerification() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [files, setFiles] = useState<Record<Slot, File | null>>({
    cnicFront: null,
    cnicBack: null,
    selfie: null,
  });
  const [progress, setProgress] = useState<Partial<Record<Slot, number>>>({});
  const [consent, setConsent] = useState(false);
  const [consentError, setConsentError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<FormError | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const job = useJobStatus(jobId);
  const complete = job.data?.status === 'complete';
  const failed = job.data?.status === 'failed' || job.data?.status === 'not_found';

  const ready = SLOTS.every((s) => files[s.key]) && consent;

  async function onSubmit() {
    if (!consent) {
      setConsentError(true);
      return;
    }
    setError(null);
    setSubmitting(true);

    try {
      // Uploaded one at a time on purpose. Three concurrent multi-megabyte
      // POSTs over a mobile connection are slower in aggregate than three
      // sequential ones, and a per-file progress bar is only honest if the
      // files are not competing for the same bandwidth.
      const ids: Partial<Record<Slot, string>> = {};
      for (const slot of SLOTS) {
        const file = files[slot.key];
        if (!file) continue;
        ids[slot.key] = await uploadFile(slot.purpose, file, {
          onProgress: (percent) => setProgress((p) => ({ ...p, [slot.key]: percent })),
        });
      }

      const result = await api.POST('/api/v1/verification/identity', {
        body: {
          cnicFrontFileId: ids.cnicFront as string,
          cnicBackFileId: ids.cnicBack as string,
          selfieFileId: ids.selfie as string,
          biometricConsent: true,
        },
      });
      if (result.error) throw toApiError(result.error);

      const data = (result.data as { data: { jobId?: string } }).data;
      setJobId(data.jobId ?? null);
      await queryClient.invalidateQueries({ queryKey: qk.verification.status });
    } catch (raw) {
      const apiError = toApiError(raw);
      setError({ message: apiError.message, requestId: apiError.requestId });
    } finally {
      setSubmitting(false);
      setProgress({});
    }
  }

  // ── Processing / result ──────────────────────────────────────────

  if (jobId) {
    return (
      <Card>
        <CardContent className="space-y-4 pt-6">
          {!complete && !failed && (
            <>
              <div className="flex items-center gap-3">
                <Spinner label="Checking your documents" />
                <p className="font-medium">Checking your documents…</p>
              </div>
              <p className="text-sm text-muted-foreground">
                We are reading your CNIC and comparing your selfie with the photo on it. This
                usually takes under a minute. You can leave this page — your score updates on its
                own.
              </p>
            </>
          )}

          {complete && (
            <>
              <Alert tone="success" title="Documents received">
                Your identity check has finished. Your Trust Score has been updated with the result.
              </Alert>
              <Button
                className="w-full"
                onClick={() => {
                  router.push('/dashboard');
                  router.refresh();
                }}
              >
                Back to dashboard
              </Button>
            </>
          )}

          {failed && (
            <>
              <Alert tone="warning" title="We could not finish the check automatically">
                A reviewer will look at your documents by hand. You do not need to upload them
                again.
              </Alert>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => router.push('/dashboard')}
              >
                Back to dashboard
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    );
  }

  // ── Capture form ─────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      <CaptureTips />

      {SLOTS.map((slot) => (
        <ImageCapture
          key={slot.key}
          id={slot.key}
          label={slot.label}
          hint={slot.hint}
          facing={slot.facing}
          value={files[slot.key]}
          onChange={(file) => setFiles((f) => ({ ...f, [slot.key]: file }))}
          progress={progress[slot.key] ?? null}
          disabled={submitting}
        />
      ))}

      <Card>
        <CardContent className="pt-6">
          <label htmlFor="biometric-consent" className="flex cursor-pointer items-start gap-3">
            <input
              id="biometric-consent"
              type="checkbox"
              checked={consent}
              disabled={submitting}
              onChange={(event) => {
                setConsent(event.target.checked);
                if (event.target.checked) setConsentError(false);
              }}
              aria-invalid={consentError ? true : undefined}
              aria-describedby={consentError ? 'consent-error consent-detail' : 'consent-detail'}
              className="mt-0.5 h-4 w-4 shrink-0 rounded border-input text-primary focus-visible:ring-2 focus-visible:ring-ring"
            />
            <span className="text-sm font-medium">
              I agree to TrustLens comparing my selfie with the photo on my CNIC.
            </span>
          </label>

          {/* Outside the label on purpose. A label is announced in full, so
              burying three sentences of detail in it makes the control far
              harder to use with a screen reader than a short label plus a
              described-by note. */}
          <p id="consent-detail" className="mt-2 pl-7 text-sm text-muted-foreground">
            This is biometric processing. We use your images only to run this check. The extracted
            details are stored encrypted, and the images themselves are deleted 90 days after a
            final decision. You can withdraw consent and delete your data at any time from your
            account settings.
          </p>

          {consentError && (
            <p id="consent-error" role="alert" className="mt-2 text-sm text-destructive">
              We cannot run the check without your consent.
            </p>
          )}
        </CardContent>
      </Card>

      <Alert tone="info">
        TrustLens checks that your CNIC looks genuine and that it matches your face. It is not a
        NADRA record check — no public service exists for that.
      </Alert>

      {error && (
        <Alert tone="error" requestId={error.requestId}>
          {error.message}
        </Alert>
      )}

      <Button
        size="lg"
        className="w-full"
        disabled={!ready || submitting}
        onClick={() => void onSubmit()}
      >
        {submitting ? 'Uploading…' : 'Submit for verification'}
      </Button>
    </div>
  );
}
