/** Reusable UI rendering and interaction component: ListingForm. */
'use client';

import { useApiForm } from '@/lib/forms/use-api-form';
import { uploadFile } from '@/lib/upload';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  areasForCity,
  LISTING_CATEGORIES,
  LISTING_CATEGORY_LABELS,
  PAKISTAN_CITIES,
} from '@trustlens/constants';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input, Spinner } from '@trustlens/ui';
import { LISTING_CONDITIONS, listingSchema, type ListingInput } from '@trustlens/validation';
import { Trash2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import type { Listing, ListingPayload } from '../hooks/use-listings';
import { LocationPicker } from './LocationPicker';

const CONDITION_LABELS: Record<(typeof LISTING_CONDITIONS)[number], string> = {
  NEW: 'New',
  LIKE_NEW: 'Like new',
  USED: 'Used',
  FOR_PARTS: 'For parts',
};

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
      condition: (listing?.condition as (typeof LISTING_CONDITIONS)[number]) ?? undefined,
      city: listing?.city ?? '',
      area: listing?.area ?? '',
      latitude: listing?.latitude ?? undefined,
      longitude: listing?.longitude ?? undefined,
      negotiable: listing?.negotiable ?? false,
      videoFileId: listing?.videoFileId ?? undefined,
    },
  });

  const { submit, formError } = useApiForm<ListingInput>(setError);

  const [attributes, setAttributes] = useState<{ key: string; value: string }[]>(
    listing?.attributes
      ? Object.entries(listing.attributes).map(([key, value]) => ({ key, value }))
      : [],
  );
  const [videoUploading, setVideoUploading] = useState(false);
  const [videoError, setVideoError] = useState<string | null>(null);

  // The area list depends on the chosen city - OLX-style cascading picker,
  // not two independent free-text fields.
  const selectedCity = watch('city');
  const areaOptions = areasForCity(selectedCity);
  const latitude = watch('latitude');
  const longitude = watch('longitude');
  const videoFileId = watch('videoFileId');
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    setValue('area', '');
  }, [selectedCity, setValue]);

  async function handleVideoSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setVideoError(null);
    setVideoUploading(true);
    try {
      const fileId = await uploadFile('LISTING_VIDEO', file);
      setValue('videoFileId', fileId);
    } catch (err) {
      setVideoError(toApiError(err).message || 'Video upload failed.');
    } finally {
      setVideoUploading(false);
      e.target.value = '';
    }
  }

  const handle = handleSubmit(async (values) => {
    let created: Listing | null = null;
    const cleanAttributes = Object.fromEntries(
      attributes
        .map(({ key, value }) => [key.trim(), value.trim()] as const)
        .filter(([key, value]) => key && value),
    );
    const ok = await submit(async () => {
      created = await onSubmit({
        title: values.title,
        description: values.description,
        // An empty form field means "no value", which the API expresses as
        // null. Sending undefined would leave the old value in place on edit.
        price: values.price ?? null,
        currency: values.currency || null,
        category: values.category ?? null,
        condition: values.condition ?? null,
        city: values.city || null,
        area: values.area || null,
        // PUT replaces every field, so the private address typed in the
        // Post-an-Ad wizard must be carried through an edit unchanged.
        addressLine: listing?.addressLine ?? null,
        latitude: values.latitude ?? null,
        longitude: values.longitude ?? null,
        negotiable: values.negotiable ?? false,
        attributes: cleanAttributes,
        videoFileId: values.videoFileId ?? null,
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

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-input"
          {...register('negotiable')}
        />
        Price is negotiable
      </label>

      <div className="grid gap-4 sm:grid-cols-2">
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

        <Field htmlFor="condition" label="Condition" error={errors.condition?.message}>
          <select
            {...fieldAria('condition', errors.condition?.message)}
            className="h-11 w-full rounded-md border border-input bg-background px-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-sm"
            {...register('condition')}
          >
            <option value="">Choose a condition…</option>
            {LISTING_CONDITIONS.map((c) => (
              <option key={c} value={c}>
                {CONDITION_LABELS[c]}
              </option>
            ))}
          </select>
        </Field>
      </div>

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

      <div className="space-y-2">
        <p className="text-sm font-medium">Specs</p>
        <p className="text-sm text-muted-foreground">
          Optional details buyers can search on - e.g. Brand / Samsung, RAM / 8GB.
        </p>
        {attributes.map((attr, index) => (
          <div key={index} className="flex gap-2">
            <Input
              aria-label="Spec name"
              placeholder="Brand"
              value={attr.key}
              onChange={(e) => {
                const next = [...attributes];
                next[index] = { ...attr, key: e.target.value };
                setAttributes(next);
              }}
            />
            <Input
              aria-label="Spec value"
              placeholder="Samsung"
              value={attr.value}
              onChange={(e) => {
                const next = [...attributes];
                next[index] = { ...attr, value: e.target.value };
                setAttributes(next);
              }}
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Remove spec"
              onClick={() => setAttributes(attributes.filter((_, i) => i !== index))}
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={attributes.length >= 20}
          onClick={() => setAttributes([...attributes, { key: '', value: '' }])}
        >
          Add spec
        </Button>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium">Video</p>
        <p className="text-sm text-muted-foreground">Required to go live: a short MP4 or WebM clip, up to 50 MB.</p>
        {videoFileId ? (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Video attached.</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setValue('videoFileId', undefined)}
            >
              Remove
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <input
              type="file"
              accept="video/mp4,video/webm"
              disabled={videoUploading}
              onChange={(e) => void handleVideoSelect(e)}
              className="text-sm"
            />
            {videoUploading && <Spinner label="Uploading video" />}
          </div>
        )}
        {videoError && <Alert tone="error">{videoError}</Alert>}
      </div>

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
