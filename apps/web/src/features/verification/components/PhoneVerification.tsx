'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { useApiForm } from '@/lib/forms/use-api-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input } from '@trustlens/ui';
import { otpSchema, phoneSchema } from '@trustlens/validation';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

const phoneForm = z.object({ phoneNumber: phoneSchema });
const codeForm = z.object({ code: otpSchema });
type PhoneInput = z.infer<typeof phoneForm>;
type CodeInput = z.infer<typeof codeForm>;

/** Seconds before a new code may be requested. */
const RESEND_SECONDS = 60;

export function PhoneVerification() {
  const [sentTo, setSentTo] = useState<string | null>(null);

  return sentTo ? (
    <CodeStep phone={sentTo} onChangeNumber={() => setSentTo(null)} />
  ) : (
    <NumberStep onSent={setSentTo} />
  );
}

function NumberStep({ onSent }: { onSent: (phone: string) => void }) {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<PhoneInput>({ resolver: zodResolver(phoneForm) });
  const { submit, formError } = useApiForm<PhoneInput>(setError);

  const onSubmit = handleSubmit(async (values) => {
    const ok = await submit(async () => {
      const result = await api.POST('/api/v1/verification/phone/request-otp', { body: values });
      if (result.error) throw toApiError(result.error);
    });
    if (ok) onSent(values.phoneNumber);
  });

  return (
    <form onSubmit={(event) => void onSubmit(event)} className="space-y-4" noValidate>
      <Field
        htmlFor="phoneNumber"
        label="Mobile number"
        error={errors.phoneNumber?.message}
        hint="Include the country code, e.g. +923001234567."
      >
        <Input
          {...fieldAria('phoneNumber', errors.phoneNumber?.message, 'hint')}
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          placeholder="+923001234567"
          {...register('phoneNumber')}
        />
      </Field>

      <Alert tone="info">
        Use a real mobile SIM. Internet (VOIP) numbers score lower, because they are cheap to
        discard and re-create.
      </Alert>

      {formError && (
        <Alert tone="error" requestId={formError.requestId}>
          {formError.message}
        </Alert>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Sending…' : 'Send code'}
      </Button>
    </form>
  );
}

function CodeStep({ phone, onChangeNumber }: { phone: string; onChangeNumber: () => void }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [secondsLeft, setSecondsLeft] = useState(RESEND_SECONDS);
  const [resent, setResent] = useState(false);
  const [verified, setVerified] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<CodeInput>({ resolver: zodResolver(codeForm) });
  const { submit, formError } = useApiForm<CodeInput>(setError);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const timer = setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [secondsLeft]);

  const onSubmit = handleSubmit(async (values) => {
    const ok = await submit(async () => {
      const result = await api.POST('/api/v1/verification/phone/verify-otp', { body: values });
      if (result.error) throw toApiError(result.error);
    });
    if (ok) {
      setVerified(true);
      await queryClient.invalidateQueries({ queryKey: qk.verification.status });
      router.refresh();
    }
  });

  async function resend() {
    setResent(false);
    const result = await api.POST('/api/v1/verification/phone/request-otp', {
      body: { phoneNumber: phone },
    });
    if (!result.error) {
      setSecondsLeft(RESEND_SECONDS);
      setResent(true);
    }
  }

  if (verified) {
    return (
      <div className="space-y-4">
        <Alert tone="success" title="Phone verified">
          {phone} is confirmed.
        </Alert>
        <Button size="lg" className="w-full" onClick={() => router.push('/dashboard')}>
          Back to dashboard
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={(event) => void onSubmit(event)} className="space-y-4" noValidate>
      <p className="text-sm text-muted-foreground">
        We sent a 6-digit code to <span className="font-medium text-foreground">{phone}</span>.{' '}
        <button
          type="button"
          onClick={onChangeNumber}
          className="text-primary underline-offset-4 hover:underline"
        >
          Use a different number
        </button>
      </p>

      <Field htmlFor="code" label="Verification code" error={errors.code?.message}>
        <Input
          {...fieldAria('code', errors.code?.message)}
          type="text"
          // `one-time-code` is what lets iOS and Android offer the code from
          // the SMS above the keyboard instead of making people switch apps.
          autoComplete="one-time-code"
          inputMode="numeric"
          maxLength={6}
          placeholder="123456"
          className="text-center text-lg tracking-[0.4em]"
          {...register('code')}
        />
      </Field>

      {resent && <Alert tone="success">A new code is on its way.</Alert>}

      {formError && (
        <Alert tone="error" requestId={formError.requestId}>
          {formError.message}
        </Alert>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Checking…' : 'Verify'}
      </Button>

      <Button
        type="button"
        variant="ghost"
        className="w-full"
        disabled={secondsLeft > 0}
        onClick={() => void resend()}
      >
        {secondsLeft > 0 ? `Resend code in ${secondsLeft}s` : 'Resend code'}
      </Button>
    </form>
  );
}
