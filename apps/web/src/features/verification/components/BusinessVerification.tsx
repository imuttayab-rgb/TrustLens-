'use client';

import { useSeller, useSetAccountType, useSubmitBusinessVerification } from '@/features/seller';
import type { FormError } from '@/lib/forms/use-api-form';
import { uploadFile } from '@/lib/upload';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Card, CardContent, Field, Input } from '@trustlens/ui';
import { useState } from 'react';
import { ImageCapture } from './ImageCapture';

/**
 * Submits a business registration/tax certificate for review (BUS-01).
 *
 * Unlike identity verification there is no AI pipeline here and so no job
 * to poll - a submission goes straight into the staff review queue and the
 * status is just whatever `GET /sellers/me` already reports.
 */
export function BusinessVerification() {
  const { data: seller } = useSeller();
  const setAccountType = useSetAccountType();
  const submitVerification = useSubmitBusinessVerification();

  const [legalName, setLegalName] = useState('');
  const [registrationNumber, setRegistrationNumber] = useState('');
  const [document, setDocument] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<FormError | null>(null);
  const [switchError, setSwitchError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  if (seller?.accountType !== 'BUSINESS') {
    return (
      <div className="space-y-3">
        <Alert tone="info" title="This is a business account feature">
          Switch to a business account to unlock the registration-document check below.
        </Alert>
        {switchError && <Alert tone="error">{switchError}</Alert>}
        <Button
          disabled={setAccountType.isPending}
          onClick={() =>
            setAccountType.mutate('BUSINESS', {
              onError: (err) => setSwitchError(toApiError(err).message),
            })
          }
        >
          {setAccountType.isPending ? 'Switching…' : 'Switch to a business account'}
        </Button>
      </div>
    );
  }

  if (seller.businessVerificationStatus === 'VERIFIED') {
    return (
      <Alert tone="success" title="Business verified">
        {seller.businessLegalName ?? 'Your business'} has been verified.
      </Alert>
    );
  }

  if (done || seller.businessVerificationStatus === 'PENDING') {
    return (
      <Alert tone="info" title="Submitted for review">
        A staff reviewer will look at your registration document by hand - there is no automated
        check for this one. You do not need to submit anything else.
      </Alert>
    );
  }

  const ready = legalName.trim().length >= 2 && registrationNumber.trim().length >= 2 && document;

  async function onSubmit() {
    if (!document) return;
    setError(null);
    setProgress(0);
    try {
      const fileId = await uploadFile('BUSINESS_REGISTRATION', document, {
        onProgress: setProgress,
      });
      await submitVerification.mutateAsync({
        legalName: legalName.trim(),
        registrationNumber: registrationNumber.trim(),
        documentFileId: fileId,
      });
      setDone(true);
    } catch (raw) {
      const apiError = toApiError(raw);
      setError({ message: apiError.message, requestId: apiError.requestId });
    } finally {
      setProgress(null);
    }
  }

  const submitting = submitVerification.isPending || progress !== null;

  return (
    <div className="space-y-6">
      {seller.businessVerificationStatus === 'REJECTED' && (
        <Alert tone="warning" title="Not approved last time">
          You can submit again with a clearer document or corrected details.
        </Alert>
      )}

      <Field htmlFor="legal-name" label="Registered legal name" required>
        <Input
          id="legal-name"
          value={legalName}
          onChange={(event) => setLegalName(event.target.value)}
          placeholder="Ahmed Electronics (Pvt) Ltd"
          disabled={submitting}
        />
      </Field>

      <Field
        htmlFor="registration-number"
        label="Business registration / tax number"
        required
        hint="e.g. your NTN or company registration number"
      >
        <Input
          id="registration-number"
          value={registrationNumber}
          onChange={(event) => setRegistrationNumber(event.target.value)}
          placeholder="1234567-8"
          disabled={submitting}
        />
      </Field>

      <ImageCapture
        id="business-document"
        label="Registration certificate"
        hint="A clear photo or scan of your business registration or tax certificate"
        value={document}
        onChange={setDocument}
        progress={progress}
        disabled={submitting}
      />

      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground">
          This goes straight to a staff reviewer - there is no automated check the way identity
          verification has, so it may take longer to hear back.
        </CardContent>
      </Card>

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
        {submitting ? 'Submitting…' : 'Submit for review'}
      </Button>
    </div>
  );
}
