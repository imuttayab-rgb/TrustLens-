/** Reusable UI rendering and interaction component: IdentityVerification. */
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
import { LiveFaceScan } from './LiveFaceScan';
import { LiveIdScan } from './LiveIdScan';
import { HoldIdFaceScan } from './HoldIdFaceScan';
import { LiveVerificationWizard } from './LiveVerificationWizard';
import { SelfieCapture } from './SelfieCapture';
import { HOLD_ID_ENABLED, LIVE_FACE_SCAN_ENABLED, LIVE_ID_SCAN_ENABLED, LIVE_WIZARD_ENABLED } from './verification-flags';

type Slot = 'cnicFront' | 'cnicBack' | 'selfie' | 'holdId';

const DOCUMENT_SLOTS: {
  key: 'cnicFront' | 'cnicBack';
  purpose: string;
  label: string;
  hint: string;
  facing: 'environment';
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
];

const SLOTS = [...DOCUMENT_SLOTS, { key: 'selfie' as const, purpose: 'SELFIE', label: 'Selfie' }];
const UPLOAD_SLOTS = HOLD_ID_ENABLED
  ? [...SLOTS, { key: 'holdId' as const, purpose: 'HOLD_ID', label: 'Holding ID' }]
  : SLOTS;

export function IdentityVerification() {
  // Full live camera mode (live CNIC + live face) uses the step-by-step
  // wizard. Installations with the live flags off keep the original form.
  if (LIVE_WIZARD_ENABLED) return <LiveVerificationWizard holdEnabled={HOLD_ID_ENABLED} />;
  return <IdentityVerificationForm />;
}

function IdentityVerificationForm() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [files, setFiles] = useState<Record<Slot, File | null>>({
    cnicFront: null,
    cnicBack: null,
    selfie: null,
    holdId: null,
  });
  const [progress, setProgress] = useState<Partial<Record<Slot, number>>>({});
  const [consent, setConsent] = useState(false);
  const [consentError, setConsentError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<FormError | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [useStandardCapture, setUseStandardCapture] = useState(false);

  const job = useJobStatus(jobId);
  const complete = job.data?.status === 'complete';
  const failed = job.data?.status === 'failed' || job.data?.status === 'not_found';

  const ready = UPLOAD_SLOTS.every((s) => files[s.key]) && consent;

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
      for (const slot of UPLOAD_SLOTS) {
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
          ...(HOLD_ID_ENABLED ? { holdIdFileId: ids.holdId as string } : {}),
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
                {HOLD_ID_ENABLED
                  ? 'We are comparing the separate CNIC front, selfie and holding-card frame. Automated processing may finish quickly, but a human must review the result before any verified identity status is assigned.'
                  : 'We are reading your CNIC and comparing your selfie with the photo on it. This usually takes under a minute. You can leave this page — your score updates on its own.'}
              </p>
            </>
          )}

          {complete && (
            <>
              <Alert tone="success" title="Documents received">
                {HOLD_ID_ENABLED
                  ? 'Card and face evidence received. Your identity remains pending until a human reviewer decides; no verification is promised by this scan.'
                  : 'Your identity check has finished. Your Trust Score has been updated with the result.'}
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
      {LIVE_ID_SCAN_ENABLED && (
        <Card>
          <CardContent className="pt-6">
            {/* Consent must precede BOTH ID and face camera access. Withdrawing
                it stops any active ID stream in the LiveIdScan component. */}
            <label htmlFor="live-id-consent" className="flex cursor-pointer items-start gap-3">
              <input
                id="live-id-consent"
                type="checkbox"
                checked={consent}
                disabled={submitting}
                onChange={(event) => {
                  setConsent(event.target.checked);
                  if (event.target.checked) setConsentError(false);
                  // Revocation invalidates previously captured in-memory files.
                  // Re-consenting must start a fresh front/back/face session.
                  if (!event.target.checked) {
                    setFiles({ cnicFront: null, cnicBack: null, selfie: null, holdId: null });
                  }
                }}
                aria-invalid={consentError ? true : undefined}
                aria-describedby={consentError ? 'live-id-consent-error' : undefined}
                className="mt-0.5 h-4 w-4 shrink-0 rounded border-input"
              />
              <span className="text-sm font-medium">
                I consent to live ID and face camera capture and comparing my face with the ID portrait.
              </span>
            </label>
            <p className="mt-2 pl-7 text-sm text-muted-foreground">
              Guided movement checks run on this device. {HOLD_ID_ENABLED ? 'Final front, back, face and holding-card stills' : 'Only the final front, back and face stills'}
              are sent to private storage for the identity check and staff review under the published retention policy.
              This is not a NADRA record or a certified document-liveness check.
            </p>
            {consentError && <p id="live-id-consent-error" role="alert" className="mt-2 text-sm text-destructive">Consent is required before verification.</p>}
          </CardContent>
        </Card>
      )}

      {LIVE_ID_SCAN_ENABLED ? (
        <Alert tone="info">
          Scan the front and back of your physical card with the webcam. Keep all corners visible,
          reduce glare and follow the left/right movement; a clear frame is saved automatically.
          No gallery upload is available in this mode. A blurry laptop webcam may need better light
          or an external USB camera; contact support if you cannot complete the scan.
        </Alert>
      ) : <CaptureTips />}

      {LIVE_ID_SCAN_ENABLED ? DOCUMENT_SLOTS.map((slot) => (
        <LiveIdScan
          key={slot.key}
          side={slot.key === 'cnicFront' ? 'front' : 'back'}
          value={files[slot.key]}
          onChange={(file) => setFiles((f) => ({ ...f, [slot.key]: file }))}
          progress={progress[slot.key] ?? null}
          disabled={submitting || !consent}
        />
      )) : DOCUMENT_SLOTS.map((slot) => (
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

      {LIVE_FACE_SCAN_ENABLED && !useStandardCapture && !LIVE_ID_SCAN_ENABLED && (
        <Card>
          <CardContent className="pt-6">
            <label htmlFor="face-scan-consent" className="flex cursor-pointer items-start gap-3">
              <input
                id="face-scan-consent"
                type="checkbox"
                checked={consent}
                disabled={submitting}
                onChange={(event) => {
                  setConsent(event.target.checked);
                  if (event.target.checked) setConsentError(false);
                }}
                className="mt-0.5 h-4 w-4 shrink-0"
              />
              <span className="text-sm">
                I consent to live camera face processing and comparison with my ID portrait.
              </span>
            </label>
            <p className="mt-2 pl-7 text-sm text-muted-foreground">
              The live pose tracker runs on this device; only a final face image is uploaded for the
              existing identity check. Images follow the account's identity-data retention settings.
            </p>
          </CardContent>
        </Card>
      )}

      {LIVE_FACE_SCAN_ENABLED && !useStandardCapture ? (
        <LiveFaceScan
          value={files.selfie}
          onChange={(file) => setFiles((f) => ({ ...f, selfie: file }))}
          progress={progress.selfie ?? null}
          disabled={submitting || !consent}
        />
      ) : (
        <SelfieCapture
          id="selfie"
          label="Selfie"
          value={files.selfie}
          onChange={(file) => setFiles((f) => ({ ...f, selfie: file }))}
          progress={progress.selfie ?? null}
          disabled={submitting}
        />
      )}

      {HOLD_ID_ENABLED && <HoldIdFaceScan
        value={files.holdId}
        onChange={(file) => setFiles((f) => ({ ...f, holdId: file }))}
        progress={progress.holdId ?? null}
        disabled={submitting || !consent}
      />}

      {LIVE_FACE_SCAN_ENABLED && !HOLD_ID_ENABLED && (
        <button
          type="button"
          disabled={submitting}
          className="text-sm text-muted-foreground underline underline-offset-4"
          onClick={() => {
            // Changing mode clears the old photo so an unscanned image cannot
            // be presented as the result of a completed live challenge.
            setFiles((f) => ({ ...f, selfie: null, holdId: null }));
            setUseStandardCapture((current) => !current);
          }}
        >
          {useStandardCapture ? 'Try live scan instead' : 'Camera issue? Use standard verification'}
        </button>
      )}

      {(!LIVE_FACE_SCAN_ENABLED || useStandardCapture) && !LIVE_ID_SCAN_ENABLED && <Card>
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
              I agree to TrustLens comparing my captured face with the photo on my CNIC.
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
      </Card>}

      <Alert tone="info">
        TrustLens checks the submitted ID's readable details and compares its portrait to your
        captured face on the server. A camera-motion challenge is not foolproof liveness, and this
        is not a NADRA record check. Demo AI settings may simulate the comparison.
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
