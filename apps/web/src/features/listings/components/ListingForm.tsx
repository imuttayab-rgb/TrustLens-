'use client';

import { useApiForm } from '@/lib/forms/use-api-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  areasForCity,
  LISTING_CATEGORIES,
  LISTING_CATEGORY_LABELS,
  PAKISTAN_CITIES,
} from '@trustlens/constants';
import { Alert, Button, Field, fieldAria, Input } from '@trustlens/ui';
import { listingSchema, type ListingInput } from '@trustlens/validation';
import { useRouter } from 'next/navigation';
import { useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import type { Listing, ListingPayload } from '../hooks/use-listings';
import { LocationPicker } from './LocationPicker';

export function ListingForm({
  listing,
  onSubmit,
  submitLabel,
  onSuccess,
}: {
  listing?: Listing | undefined;
  onSubmit: (payload: ListingPayload) => Promise<Listing>;
  submitLabel: string;
  /** Overrides the default "navigate to the listing's detail page" behaviour. */
  onSuccess?: (listing: Listing) => void;
}) {
  const router = useRouter();

  const {
    register,
    handleSubmit,
    setError,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<ListingInput>({
    resolver: zodResolver(listingSchema),
    defaultValues: {
      title: listing?.title ?? '',
      description: listing?.description ?? '',
      price: listing?.price ?? undefined,
      currency: listing?.currency ?? 'PKR',
      category: listing?.category ?? undefined,
      city: listing?.city ?? '',
      area: listing?.area ?? '',
      latitude: listing?.latitude ?? undefined,
      longitude: listing?.longitude ?? undefined,
    },
  });

  const { submit, formError } = useApiForm<ListingInput>(setError);

  // The area list depends on the chosen city - OLX-style cascading picker,
  // not two independent free-text fields.
  const selectedCity = watch('city');
  const areaOptions = areasForCity(selectedCity);
  const latitude = watch('latitude');
  const longitude = watch('longitude');
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    setValue('area', '');
  }, [selectedCity, setValue]);

  const handle = handleSubmit(async (values) => {
    let created: Listing | null = null;
    const ok = await submit(async () => {
      created = await onSubmit({
        title: values.title,
        description: values.description,
        // An empty form field means "no value", which the API expresses as
        // null. Sending undefined would leave the old value in place on edit.
        price: values.price ?? null,
        currency: values.currency || null,
        category: values.category ?? null,
        city: values.city || null,
        area: values.area || null,
        latitude: values.latitude ?? null,
        longitude: values.longitude ?? null,
      });
    });
    if (ok && created) {
      if (onSuccess) {
        onSuccess(created);
      } else {
        router.push(`/dashboard/listings/${(created as Listing).id}`);
        router.refresh();
      }
    }
  });

  return (
    <form onSubmit={(event) => void handle(event)} className="space-y-4" noValidate>
      <Field htmlFor="title" label="Title" required error={errors.title?.message}>
        <Input
          {...fieldAria('title', errors.title?.message)}
          autoComplete="off"
          placeholder="Honda City 2018, low mileage"
          {...register('title')}
        />
      </Field>

      <Field
        htmlFor="description"
        label="Description"
        required
        error={errors.description?.message}
        hint="Be specific. Vague descriptions score worse, because scammers write them."
      >
        <textarea
          {...fieldAria('description', errors.description?.message, 'hint')}
          rows={6}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring aria-[invalid=true]:border-destructive sm:text-sm"
          {...register('description')}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field htmlFor="price" label="Price" error={errors.price?.message}>
          <Input
            {...fieldAria('price', errors.price?.message)}
            type="number"
            inputMode="decimal"
            min={0}
            step="any"
            placeholder="185000"
            {...register('price')}
          />
        </Field>

        <Field htmlFor="currency" label="Currency" error={errors.currency?.message}>
          <Input
            {...fieldAria('currency', errors.currency?.message)}
            maxLength={3}
            placeholder="PKR"
            {...register('currency')}
          />
        </Field>
      </div>

      <Field
        htmlFor="category"
        label="Category"
        error={errors.category?.message}
        hint="Your price is compared against other listings in this category."
      >
        {/* A fixed list, not free text: the price signal compares a listing
            against the median of its own category, and free text splits one
            category into several buckets that never pool. */}
        <select
          {...fieldAria('category', errors.category?.message, 'hint')}
          className="h-11 w-full rounded-md border border-input bg-background px-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-sm"
          {...register('category')}
        >
          <option value="">Choose a category…</option>
          {LISTING_CATEGORIES.map((slug) => (
            <option key={slug} value={slug}>
              {LISTING_CATEGORY_LABELS[slug]}
            </option>
          ))}
        </select>
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field htmlFor="city" label="City" error={errors.city?.message}>
          {/* A fixed list, like category - the same buyer picking a city on
              Browse must land on the same value a seller picked here. */}
          <select
            {...fieldAria('city', errors.city?.message)}
            className="h-11 w-full rounded-md border border-input bg-background px-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-sm"
            {...register('city')}
          >
            <option value="">Choose a city…</option>
            {PAKISTAN_CITIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>

        <Field htmlFor="area" label="Area" error={errors.area?.message}>
          <select
            {...fieldAria('area', errors.area?.message)}
            disabled={!selectedCity}
            className="h-11 w-full rounded-md border border-input bg-background px-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 sm:text-sm"
            {...register('area')}
          >
            <option value="">{selectedCity ? 'Choose an area…' : 'Choose a city first'}</option>
            {areaOptions.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <LocationPicker
        latitude={latitude ?? null}
        longitude={longitude ?? null}
        onChange={(lat, lng) => {
          setValue('latitude', lat);
          setValue('longitude', lng);
        }}
      />

      {formError && (
        <Alert tone="error" requestId={formError.requestId}>
          {formError.message}
        </Alert>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Saving…' : submitLabel}
      </Button>
    </form>
  );
}
