'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { useApiForm } from '@/lib/forms/use-api-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input } from '@trustlens/ui';
import { becomeSellerSchema, type BecomeSellerInput } from '@trustlens/validation';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';

/**
 * Preview of the public handle the backend will derive.
 *
 * Kept deliberately close to `slugify_handle` in the domain policy. It is a
 * preview, not a promise: if the handle is already taken the server appends a
 * suffix, which the copy below says out loud rather than letting the seller
 * discover a different URL after submitting.
 */
function previewHandle(displayName: string): string {
  const slug = displayName
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/-{2,}/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 40)
    .replace(/-$/, '');
  return slug || 'seller';
}

export function BecomeSellerForm() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    setError,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<BecomeSellerInput>({
    resolver: zodResolver(becomeSellerSchema),
    defaultValues: {
      displayName: '',
      businessType: '',
      city: '',
      countryCode: 'PK',
      accountType: 'INDIVIDUAL',
    },
  });

  const { submit, formError } = useApiForm<BecomeSellerInput>(setError);
  const displayName = watch('displayName');

  const onSubmit = handleSubmit(async (values) => {
    const ok = await submit(async () => {
      const result = await api.POST('/api/v1/me/become-seller', {
        body: {
          displayName: values.displayName,
          // Empty optional fields are omitted rather than sent as "": the
          // API rejects a 2-character country code that is zero characters.
          ...(values.businessType ? { businessType: values.businessType } : {}),
          ...(values.city ? { city: values.city } : {}),
          ...(values.countryCode ? { countryCode: values.countryCode.toUpperCase() } : {}),
          ...(values.accountType ? { accountType: values.accountType } : {}),
        },
      });
      if (result.error) throw toApiError(result.error);
    });

    if (ok) {
      // Becoming a seller grants the SELLER role, so the cached "who am I"
      // and "do I have a seller profile" answers are both stale. Without
      // dropping them the dashboard renders the no-profile state it just left.
      await queryClient.invalidateQueries({ queryKey: qk.me });
      await queryClient.invalidateQueries({ queryKey: qk.seller.me });
      await queryClient.invalidateQueries({ queryKey: qk.verification.status });
      router.push('/dashboard');
      router.refresh();
    }
  });

  return (
    <form onSubmit={(event) => void onSubmit(event)} className="space-y-4" noValidate>
      <Field
        htmlFor="displayName"
        label="Display name"
        required
        error={errors.displayName?.message}
        hint="This is the name buyers see. Use the name you actually trade under."
      >
        <Input
          {...fieldAria('displayName', errors.displayName?.message)}
          autoComplete="organization"
          placeholder="Ahmed Electronics"
          {...register('displayName')}
        />
      </Field>

      {displayName.trim().length >= 2 && !errors.displayName && (
        <p className="text-sm text-muted-foreground">
          Your public page will be{' '}
          <span className="font-medium text-foreground">/seller/{previewHandle(displayName)}</span>.
          If that address is taken we add a number to the end.
        </p>
      )}

      <Field
        htmlFor="accountType"
        label="Account type"
        hint="A business account unlocks a registration-document verification step, shown as a badge on your storefront once approved."
      >
        <select
          {...fieldAria('accountType')}
          className="h-11 w-full rounded-md border border-input bg-background px-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-sm"
          {...register('accountType')}
        >
          <option value="INDIVIDUAL">Individual</option>
          <option value="BUSINESS">Business / company</option>
        </select>
      </Field>

      <Field htmlFor="businessType" label="Business type" error={errors.businessType?.message}>
        <Input
          {...fieldAria('businessType', errors.businessType?.message)}
          autoComplete="off"
          placeholder="Individual, shop, wholesaler"
          {...register('businessType')}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field htmlFor="city" label="City" error={errors.city?.message}>
          <Input
            {...fieldAria('city', errors.city?.message)}
            autoComplete="address-level2"
            placeholder="Lahore"
            {...register('city')}
          />
        </Field>

        <Field
          htmlFor="countryCode"
          label="Country"
          error={errors.countryCode?.message}
          hint="Two-letter code, e.g. PK."
        >
          <Input
            {...fieldAria('countryCode', errors.countryCode?.message)}
            autoComplete="country"
            maxLength={2}
            placeholder="PK"
            className="uppercase"
            {...register('countryCode')}
          />
        </Field>
      </div>

      {formError && (
        <Alert tone="error" requestId={formError.requestId}>
          {formError.message}
        </Alert>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Creating your profile…' : 'Create seller profile'}
      </Button>

      <p className="text-xs text-muted-foreground">
        Creating a profile does not publish anything yet. Your Trust Score stays private until you
        complete at least one verification check.
      </p>
    </form>
  );
}
