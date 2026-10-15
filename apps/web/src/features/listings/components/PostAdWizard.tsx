/** Reusable UI rendering and interaction component: PostAdWizard. */
'use client';
import { useUnsavedChanges } from './use-unsaved-changes';
import { useDraftRecovery } from './draft-recovery';

import { CategoryChooser } from '@/features/categories';
import { CategoryFields, isCategoryField } from '@/features/categories';
import { useMyProfile } from '@/features/profile';
import {
  categoryNode,
  categoryPath,
  categoryGuidance,
  categoryFieldErrors,
  specKey,
  type CategoryNode,
  type CategoryField,
} from '@trustlens/constants';
import { useLocale } from 'next-intl';
import { AdAssistant } from '@/features/assistant';
import type { AdContent } from '@/features/assistant';
import { SmartSearch } from '@/features/assistant';
import { useSeller } from '@/features/seller';
import { toApiError } from '@trustlens/api-client';
import { LISTING_CATEGORY_LABELS, type ListingCategory } from '@trustlens/constants';
import { Alert, Button, Spinner } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  Heart,
  MapPin,
  Play,
  Plus,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
  XCircle,
} from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  useAnalyseListing,
  useCreateListing,
  useListing,
  useListingImages,
  useUpdateListing,
  type Listing,
  type ListingPayload,
} from '../hooks/use-listings';
import { PostAdLocationStep, type LocationValue } from './PostAdLocationStep';
import { PostAdMediaStep, type AttachedVideo } from './PostAdMediaStep';
import {
  furthestReachableStep,
  missingForPublish,
  MISSING_LABEL,
  POST_AD_STEPS,
} from './post-ad-helpers';

import {
  acceptDetected,
  addSpec,
  createEditor,
  editForm,
  editSpec,
  removeSpec,
  replaceContent,
  specFeedback,
  undoContent,
  type Editor,
} from './spec-editor';

const CONDITIONS = [
  ['NEW', 'New'],
  ['LIKE_NEW', 'Like new'],
  ['USED', 'Used'],
  ['FOR_PARTS', 'For parts'],
] as const;

interface DetailsValue {
  title: string;
  description: string;
  category: ListingCategory | '';
  categoryNodeId: string | null;
  showPhone: boolean;
  condition: string;
  price: string;
  negotiable: boolean;
  specs: { key: string; value: string }[];
}

const inputClass =
  'h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring aria-[invalid=true]:border-destructive';

function detailsFrom(listing: Listing | undefined): DetailsValue {
  return {
    title: listing?.title ?? '',
    description: listing?.description ?? '',
    category: listing?.category ?? '',
    categoryNodeId: listing?.categoryNodeId ?? null,
    showPhone: listing?.showPhone ?? false,
    condition: listing?.condition ?? '',
    price: listing?.price !== null && listing?.price !== undefined ? String(listing.price) : '',
    negotiable: listing?.negotiable ?? false,
    specs: listing?.attributes
      ? Object.entries(listing.attributes).map(([key, value]) => ({ key, value }))
      : [],
  };
}

function detailsErrors(d: DetailsValue): Partial<Record<keyof DetailsValue, string>> {
  const errors: Partial<Record<keyof DetailsValue, string>> = {};
  if (d.title.trim().length < 3) errors.title = 'Enter a title (at least 3 characters).';
  if (d.description.trim().length < 10)
    errors.description = 'Describe the item in at least 10 characters.';
  if (!d.category) errors.category = 'Choose a category.';
  if ((!d.categoryNodeId || categoryNode(d.categoryNodeId)?.conditionRequired) && !d.condition)
    errors.condition = 'Choose a condition.';
  const price = Number(d.price);
  if (
    (d.price.trim() === '' &&
      categoryNode(d.categoryNodeId)?.policy !== 'job' &&
      categoryNode(d.categoryNodeId)?.policy !== 'service') ||
    !Number.isFinite(price) ||
    price < 0
  )
    errors.price = 'Enter a price in PKR.';
  return errors;
}

/**
 * The 4-step "Post an Ad" wizard (Post-an-Ad v2).
 *
 * 1 Details -> saves a PRIVATE draft (POST), so photos and the video can be
 *   attached to a real listing id. 2 Photos & Video. 3 Location (full private
 *   address + map pin). 4 Preview & Publish -> asks the worker to run the
 *   safety analysis; the backend makes the ad live only when the seller is
 *   verified AND the ad has a photo, a video and a full location.
 *
 * Every save is a full PUT built from all current values, because the API
 * replaces every field on update.
 */
export function PostAdWizard({
  initialListingId = null,
  mode = 'create',
}: {
  initialListingId?: string | null;
  mode?: 'create' | 'edit';
}) {
  const ur = useLocale() === 'ur';
  const { data: profile } = useMyProfile();
  const router = useRouter();
  const [listingId, setListingId] = useState<string | null>(initialListingId);
  const existing = useListing(listingId);
  const { data: images = [] } = useListingImages(listingId);
  const { data: seller } = useSeller();
  const create = useCreateListing();
  const update = useUpdateListing(listingId ?? 'none');
  const analyse = useAnalyseListing();

  const [step, setStep] = useState(0);
  const [dirty, setDirty] = useState(false);
  useUnsavedChanges(dirty);
  const [editor, setEditor] = useState(() => createEditor(detailsFrom(undefined)));
  const editorRef = useRef(editor);
  editorRef.current = editor;
  const details = editor.details;
  const selectedCategory = categoryNode(details.categoryNodeId);
  const virtual =
    selectedCategory?.policy === 'service' ||
    selectedCategory?.policy === 'job' ||
    selectedCategory?.policy === 'transfer';
  const [choosingCategory, setChoosingCategory] = useState(initialListingId === null);
  const [pendingCategory, setPendingCategory] = useState<CategoryNode | null>(null);
  const categoryDrafts = useRef(new Map<string, Editor<DetailsValue>>());
  function chooseCategory(node: CategoryNode) {
    if (details.categoryNodeId === node.id) {
      setChoosingCategory(false);
      return;
    }
    if (details.title || details.description || details.specs.length) {
      setPendingCategory(node);
      return;
    }
    applyCategory(node);
  }
  function applyCategory(node: CategoryNode) {
    setDirty(true);
    categoryDrafts.current.set(details.categoryNodeId ?? 'legacy', editor);
    const cached = categoryDrafts.current.get(node.id);
    setEditor(
      cached
        ? editForm(cached, {
            ...cached.details,
            title: details.title,
            description: details.description,
          })
        : createEditor({
            ...details,
            category: node.legacyCategory as ListingCategory,
            categoryNodeId: node.id,
            condition: '',
            specs: [],
          }),
    );
    setChoosingCategory(false);
    setPendingCategory(null);
    setStep(0);
    setPublished(false);
    setSavedAt(null);
  }
  function changeCategoryField(field: CategoryField, value: string) {
    changeEditor((current) => {
      const i = current.details.specs.findIndex((s) =>
        [specKey(field.label), specKey(field.key)].includes(specKey(s.key)),
      );
      if (i >= 0) return editSpec(current, i, { key: field.label, value });
      if (!value || current.details.specs.length >= 20) return current;
      return editSpec(addSpec(current), current.details.specs.length, { key: field.label, value });
    });
  }
  const [location, setLocation] = useState<LocationValue>({
    addressLine: '',
    city: '',
    area: '',
    latitude: null,
    longitude: null,
  });
  const [video, setVideo] = useState<AttachedVideo | null>(null);
  const [hydrated, setHydrated] = useState(initialListingId === null);
  const [showErrors, setShowErrors] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [published, setPublished] = useState(false);
  const recovery = useDraftRecovery({
    userId: profile?.userId,
    listingId,
    hydrated,
    dirty,
    published,
    editor,
    categories: categoryDrafts.current,
  });
  const aiUndo = editor.undo
    ? {
        before: {
          description: editor.undo.before.details.description,
          specs: editor.undo.before.details.specs,
        },
        after: editor.undo.after,
      }
    : null;
  const feedback = useMemo(() => specFeedback(editor), [editor]);

  function changeEditor(change: (current: Editor<DetailsValue>) => Editor<DetailsValue>) {
    setDirty(true);
    setEditor(change);
    setSavedAt(null);
  }
  function setDetails(next: DetailsValue | ((current: DetailsValue) => DetailsValue)) {
    changeEditor((current) =>
      editForm(current, typeof next === 'function' ? next(current.details) : next),
    );
  }
  function replaceAdContent(next: AdContent): AdContent {
    // Price/negotiable edits do not cancel AI. Preserve their latest values too.
    setDirty(true);
    const replaced = replaceContent(editorRef.current, next);
    setEditor(replaced);
    setSavedAt(null);
    return { description: replaced.details.description, specs: replaced.details.specs };
  }
  function undoAdContent() {
    changeEditor(undoContent);
  }

  // Resume an existing draft (?listing=<id>) exactly where it was left.
  useEffect(() => {
    if (hydrated || !existing.data) return;
    const l = existing.data;
    setEditor(createEditor(detailsFrom(l)));
    setLocation({
      addressLine: l.addressLine ?? '',
      city: l.city ?? '',
      area: l.area ?? '',
      latitude: l.latitude,
      longitude: l.longitude,
    });
    setVideo(
      l.videoFileId
        ? {
            fileId: l.videoFileId,
            previewUrl: null,
            durationSeconds: null,
            sizeBytes: null,
            type: null,
          }
        : null,
    );
    setHydrated(true);
  }, [existing.data, hydrated]);

  // Release blob URLs for recorded/selected clips when they are replaced.
  useEffect(() => {
    const url = video?.previewUrl;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [video?.previewUrl]);

  const errors = detailsErrors(details);
  const descriptionEditor = (
    <div className="space-y-2 text-sm font-medium md:col-span-2">
      <span className="flex justify-between">
        <span>
          <label htmlFor="listing-description">
            Description <span className="text-destructive">*</span>
          </label>
        </span>
        <span className="text-xs font-normal text-muted-foreground">
          {details.description.length}/8000
        </span>
      </span>
      <textarea
        id="listing-description"
        value={details.description}
        maxLength={8000}
        rows={5}
        aria-invalid={showErrors && Boolean(errors.description)}
        disabled={busy !== null || published}
        onChange={(e) => setDetails({ ...details, description: e.target.value })}
        placeholder="Describe your item, its condition, known faults and included accessories. You can use Replace with AI below when ready."
        className={`${inputClass} h-auto py-2`}
      />
      <AdAssistant
        title={details.title}
        category={details.category}
        categoryNodeId={details.categoryNodeId}
        condition={details.condition}
        description={details.description}
        specs={details.specs}
        listingId={listingId}
        photoRevision={images.map((image) => image.imageId).join(',')}
        undo={aiUndo}
        onReplace={replaceAdContent}
        onUndo={undoAdContent}
        disabled={busy !== null || published || feedback.conflicts.length > 0}
      />
      {showErrors && errors.description && (
        <p className="text-xs text-destructive">{errors.description}</p>
      )}
    </div>
  );
  const productDetailsEditor = (
    <div className="mt-6 border-t border-border pt-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          {selectedCategory
            ? `${ur ? selectedCategory.labelUr : selectedCategory.label} · ${ur ? 'تفصیلات' : 'details'}`
            : 'Product details (optional)'}
        </h3>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => changeEditor(addSpec)}
          disabled={details.specs.length >= 20 || busy !== null || published}
        >
          <Plus className="mr-1 h-3.5 w-3.5" aria-hidden="true" /> Add detail
        </Button>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Details you write in the description appear here automatically. Review them before
        publishing; you can edit or remove any detail.
      </p>
      {details.categoryNodeId && (
        <CategoryFields
          nodeId={details.categoryNodeId}
          specs={details.specs}
          onChange={changeCategoryField}
          disabled={busy !== null || published}
        />
      )}
      <div className="mt-3 space-y-2">
        {details.specs.map((spec, i) => (
          <div
            key={i}
            className={cn(
              'grid grid-cols-[1fr_1fr_auto] gap-2',
              details.categoryNodeId && isCategoryField(details.categoryNodeId, spec) && 'hidden',
            )}
          >
            <input
              aria-label={`Detail ${i + 1} name`}
              value={spec.key}
              maxLength={40}
              placeholder="Storage"
              disabled={busy !== null || published}
              onChange={(e) =>
                changeEditor((current) => editSpec(current, i, { key: e.target.value }))
              }
              className={inputClass}
            />
            <input
              aria-label={`Detail ${i + 1} value`}
              value={spec.value}
              maxLength={80}
              placeholder="256 GB"
              disabled={busy !== null || published}
              onChange={(e) =>
                changeEditor((current) => editSpec(current, i, { value: e.target.value }))
              }
              className={inputClass}
            />
            <Button
              type="button"
              variant="ghost"
              aria-label={`Remove detail ${i + 1}`}
              disabled={busy !== null || published}
              onClick={() => changeEditor((current) => removeSpec(current, i))}
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        ))}
      </div>
      {feedback.conflicts.length > 0 && (
        <div className="mt-3 space-y-2 text-xs text-amber-600" role="status">
          {feedback.conflicts.map((conflict) => (
            <p key={conflict.index}>
              {conflict.key}: your detail says “{conflict.current}”; your text says “
              {conflict.detected}”. Edit the description or{' '}
              <button
                type="button"
                className="font-semibold underline"
                disabled={busy !== null || published}
                onClick={() => changeEditor((current) => acceptDetected(current, conflict.index))}
              >
                use “{conflict.detected}”
              </button>
              .
            </p>
          ))}
        </div>
      )}
      {feedback.ambiguous.length > 0 && (
        <p className="mt-2 text-xs text-amber-600" role="status">
          More than one value found for {feedback.ambiguous.join(', ')}. Clarify the description or
          enter the correct detail yourself.
        </p>
      )}
      {feedback.overflow && details.specs.length >= 20 && (
        <p className="mt-2 text-xs text-muted-foreground">
          All 20 detail slots are in use. Extra information stays in your description; remove an
          unwanted detail to make room.
        </p>
      )}
    </div>
  );
  const categoryErrors = categoryFieldErrors(details.categoryNodeId, details.specs, true);
  const detailsValid =
    Object.keys(errors).length === 0 &&
    categoryErrors.length === 0 &&
    feedback.conflicts.length === 0 &&
    feedback.ambiguous.length === 0;
  const missing = missingForPublish({
    photoCount: images.length,
    policy: virtual ? 'virtual' : 'physical',
    hasVideo: Boolean(video),
    latitude: location.latitude,
    longitude: location.longitude,
    addressLine: location.addressLine,
  });
  const reachable = furthestReachableStep({
    hasDraft: Boolean(listingId),
    photoCount: images.length,
    policy: virtual ? 'virtual' : 'physical',
    hasVideo: Boolean(video),
  });

  function payload(overrides: Partial<{ videoFileId: string | null }> = {}): ListingPayload {
    const attributes = Object.fromEntries(
      details.specs
        .map(({ key, value }) => [key.trim(), value.trim()] as const)
        .filter(([key, value]) => key && value),
    );
    return {
      title: details.title.trim(),
      description: details.description.trim(),
      price: details.price.trim() === '' ? null : Number(details.price),
      currency: 'PKR',
      category: details.category || null,
      categoryNodeId: details.categoryNodeId,
      showPhone: details.showPhone,
      condition: details.condition || null,
      city: location.city || null,
      area: location.area || null,
      addressLine: location.addressLine.trim() || null,
      latitude: location.latitude,
      longitude: location.longitude,
      countryCode: 'PK',
      negotiable: details.negotiable,
      attributes,
      videoFileId:
        overrides.videoFileId !== undefined ? overrides.videoFileId : (video?.fileId ?? null),
    };
  }

  async function save(label: string, overrides?: Partial<{ videoFileId: string | null }>) {
    setBusy(label);
    setError(null);
    try {
      let saved: Listing;
      if (!listingId) {
        saved = await create.mutateAsync(payload(overrides));
        recovery.clear();
        setListingId(saved.id);
        // Keep the URL resumable without a full navigation.
        window.history.replaceState(null, '', `/dashboard/listings/new?listing=${saved.id}`);
      } else {
        saved = await update.mutateAsync(payload(overrides));
      }
      setSavedAt(new Date());
      setDirty(false);
      return saved;
    } catch (err) {
      setError(toApiError(err).message || 'Could not save your ad. Try again.');
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function next() {
    if (step === 0) {
      if (!detailsValid) {
        setShowErrors(true);
        return;
      }
      if (await save('Saving draft...')) setStep(1);
      return;
    }
    if (step === 1) {
      if (!virtual && (images.length < 1 || !video)) {
        setError('Add at least 1 photo and a product video to continue.');
        return;
      }
      setError(null);
      setStep(2);
      return;
    }
    if (step === 2) {
      if ((!virtual && missing.includes('location')) || !location.city) {
        setError('Enter your full address, choose the city and place the pin on the map.');
        return;
      }
      if (await save('Saving location...')) setStep(3);
    }
  }

  async function publish() {
    if (!listingId || missing.length > 0 || !detailsValid || (virtual && !location.city)) return;
    const saved = await save('Saving...');
    if (!saved) return;
    setBusy('Starting safety check...');
    try {
      await analyse.mutateAsync(listingId);
      setPublished(true);
    } catch (err) {
      setError(toApiError(err).message || 'Could not start the safety check.');
    } finally {
      setBusy(null);
    }
  }

  const status = existing.data?.status;
  const sellerVerified =
    seller?.identityStatus === 'VERIFIED' &&
    seller?.phoneStatus === 'VERIFIED' &&
    seller?.emailStatus === 'VERIFIED' &&
    !seller?.isFlagged &&
    Boolean(profile?.canInteract);

  // "Finish verification" opens the first unfinished step. There is no page at
  // the bare /dashboard/verification path (only identity/phone/email/business).
  const verifyHref =
    seller?.identityStatus !== 'VERIFIED'
      ? '/dashboard/verification/identity'
      : seller?.phoneStatus !== 'VERIFIED'
        ? '/dashboard/verification/phone'
        : seller?.emailStatus !== 'VERIFIED'
          ? '/dashboard/verification/email'
          : '/dashboard/verification/identity';
  const goLiveChecks = [
    ...(!virtual
      ? [
          { ok: images.length >= 1, label: 'At least 1 photo' },
          { ok: Boolean(video), label: 'Product video (10-60 s)' },
        ]
      : []),
    {
      ok: virtual ? Boolean(location.city) : !missing.includes('location'),
      label: virtual ? 'Service / job city' : 'Full address + map pin',
    },
    { ok: sellerVerified, label: 'Seller verified (ID, phone, email)' },
    {
      ok: status === 'ACTIVE' && Boolean(existing.data?.analysis),
      label:
        status === 'ANALYSING' || published
          ? 'Safety analysis requested — awaiting result'
          : 'Safety analysis and publication approved',
    },
  ];

  if (initialListingId && existing.isError && !hydrated)
    return (
      <Alert tone="error" title="Your draft could not be loaded">
        <p>Your saved listing has not been changed.</p>
        <Button onClick={() => void existing.refetch()} className="mt-3">
          Try again
        </Button>
      </Alert>
    );
  if (initialListingId && !hydrated) {
    return (
      <div className="py-16">
        <Spinner label="Loading your draft..." />
      </div>
    );
  }

  if (recovery.recovery)
    return (
      <section
        className="mx-auto max-w-xl space-y-4 rounded-2xl border border-border bg-card p-6"
        aria-label={ur ? 'مسودہ بحال کریں' : 'Recover your draft'}
      >
        <h1 className="text-xl font-semibold">
          {ur ? 'اس ٹیب میں آپ کا مسودہ محفوظ ہے' : 'Your draft is saved in this tab'}
        </h1>
        <p className="text-sm text-muted-foreground">
          {ur
            ? 'اس وزٹ کا غیر محفوظ متن بحال کریں؟ اکاؤنٹ کی تصاویر اور مقام برقرار رہیں گے۔ ریفریش کے بعد رکھنے کے لیے مسودہ محفوظ کریں۔'
            : 'Recover unsaved text from this visit? Photos and location saved to your account stay in place. Use Save draft to keep edits after a refresh.'}
        </p>
        <p className="text-xs text-muted-foreground">
          {new Date(recovery.recovery.at).toLocaleString(ur ? 'ur-PK' : 'en-PK')}
        </p>
        <div className="flex gap-3">
          <Button
            onClick={() => {
              const cached = recovery.recovery!;
              setEditor(cached.editor);
              categoryDrafts.current = new Map(cached.categories);
              setDirty(true);
              setChoosingCategory(!cached.editor.details.categoryNodeId);
              recovery.accept();
            }}
          >
            {ur ? 'بحال کریں' : 'Restore draft'}
          </Button>
          <Button variant="outline" onClick={recovery.clear}>
            {ur ? 'چھوڑ دیں' : 'Discard recovery'}
          </Button>
        </div>
      </section>
    );
  if (choosingCategory)
    return (
      <div className="space-y-4">
        <CategoryChooser
          onSelect={chooseCategory}
          {...(details.category || listingId
            ? {
                onCancel: () => {
                  setChoosingCategory(false);
                  setPendingCategory(null);
                },
              }
            : {})}
        />
        {pendingCategory && (
          <Alert tone="warning" title={ur ? 'کیٹیگری تبدیل کریں؟' : 'Change category?'}>
            <p>
              {ur
                ? 'عنوان، تفصیل، تصاویر اور مقام برقرار رہیں گے۔ ہر کیٹیگری کے خانے اس ٹیب میں محفوظ رہیں گے۔ نئی تفصیلات چیک کریں؛ محفوظ اشتہار صرف سیو کرنے پر بدلے گا۔'
                : 'Your title, description, photos and location are kept. Each category’s fields are retained in this tab. Review the new fields before saving. Your saved ad changes only when you save.'}
            </p>
            <div className="mt-3 flex gap-3">
              <Button onClick={() => applyCategory(pendingCategory)}>
                {ur ? pendingCategory.labelUr + ' منتخب کریں' : 'Use ' + pendingCategory.label}
              </Button>
              <Button variant="outline" onClick={() => setPendingCategory(null)}>
                {ur ? 'موجودہ کیٹیگری رکھیں' : 'Keep current category'}
              </Button>
            </div>
          </Alert>
        )}
      </div>
    );

  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link
            href="/dashboard/listings"
            className="text-sm text-muted-foreground hover:underline"
          >
            ← Back to selling
          </Link>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">
            {mode === 'edit' ? 'Edit your ad' : 'Post an Ad'}
          </h1>
        </div>
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-brand">
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          {savedAt
            ? `Draft saved privately · ${savedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
            : listingId
              ? 'Private draft'
              : 'Nothing is public until you publish'}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 text-sm">
        <span>
          {details.categoryNodeId
            ? categoryPath(details.categoryNodeId)
                .map((n) => (ur ? n.labelUr : n.label))
                .join(' / ')
            : LISTING_CATEGORY_LABELS[details.category as ListingCategory]}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setChoosingCategory(true)}
          disabled={busy !== null || published}
        >
          {ur ? 'قسم تبدیل کریں' : 'Change category'}
        </Button>
      </div>
      {categoryErrors.length > 0 && showErrors && (
        <Alert tone="error" title="Review category details" className="mt-4">
          {categoryErrors.join(' ')}
        </Alert>
      )}
      {(feedback.conflicts.length > 0 || feedback.ambiguous.length > 0) && (
        <Alert tone="warning" title="Confirm conflicting specifications" className="mt-4">
          Review the marked details below before continuing. Your confirmed values are kept.
        </Alert>
      )}
      {virtual && (
        <p className="mt-3 text-sm text-muted-foreground">
          {ur
            ? 'اس زمرے میں تصاویر اور ویڈیو اختیاری ہیں۔ تصدیق اور حفاظتی جانچ لازمی ہے۔'
            : 'For this non-physical category, supporting media is optional; city and category details are required. Profile verification and safety checks still apply.'}
        </p>
      )}
      {/* ── Stepper ─────────────────────────────────────────────────── */}
      <ol className="mt-5 grid grid-cols-4 gap-2 rounded-xl border border-border bg-card p-3 shadow-sm sm:p-4">
        {POST_AD_STEPS.map((s, i) => {
          const done = i < step;
          const active = i === step;
          const open = i <= reachable && !published;
          return (
            <li key={s.id} className="min-w-0">
              <button
                type="button"
                disabled={!open || busy !== null}
                onClick={() => setStep(i)}
                className="flex w-full items-center gap-2 text-left disabled:cursor-not-allowed"
                aria-current={active ? 'step' : undefined}
              >
                <span
                  className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold',
                    done && 'border-brand bg-brand text-white',
                    active && 'border-brand bg-brand text-white ring-4 ring-brand/15',
                    !done && !active && 'border-border text-muted-foreground',
                  )}
                >
                  {done ? <Check className="h-4 w-4" aria-hidden="true" /> : i + 1}
                </span>
                <span
                  className={cn(
                    'hidden truncate text-sm sm:block',
                    active
                      ? 'font-semibold text-brand'
                      : done
                        ? 'text-foreground'
                        : 'text-muted-foreground',
                  )}
                >
                  {s.label}
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-5">
          {error && (
            <Alert tone="error" title="Please check">
              {error}
            </Alert>
          )}

          {step === 0 && (
            <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
              <h2 className="text-base font-semibold">Basic information</h2>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="space-y-1 text-sm font-medium md:col-span-2">
                  <span className="flex justify-between">
                    <span>
                      Title <span className="text-destructive">*</span>
                    </span>
                    <span className="text-xs font-normal text-muted-foreground">
                      {details.title.length}/80
                    </span>
                  </span>
                  <SmartSearch
                    value={details.title}
                    maxLength={80}
                    label="Listing title"
                    seller
                    category={details.category || null}
                    invalid={showErrors && Boolean(errors.title)}
                    onChange={(title) => setDetails((current) => ({ ...current, title }))}
                    onSelect={(_title, category) => {
                      if (category && !details.categoryNodeId)
                        setDetails((current) => ({
                          ...current,
                          category: category as ListingCategory,
                        }));
                    }}
                    placeholder="Product, exact model or listing title"
                    className={inputClass}
                  />
                  {showErrors && errors.title && (
                    <p className="text-xs text-destructive">{errors.title}</p>
                  )}
                </label>

                <label
                  className={cn(
                    'space-y-1 text-sm font-medium',
                    selectedCategory && !selectedCategory.conditionRequired && 'hidden',
                  )}
                >
                  <span>
                    Condition <span className="text-destructive">*</span>
                  </span>
                  <select
                    value={details.condition}
                    aria-invalid={showErrors && Boolean(errors.condition)}
                    onChange={(e) => setDetails({ ...details, condition: e.target.value })}
                    className={inputClass}
                  >
                    <option value="">Choose a condition</option>
                    {CONDITIONS.map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  {showErrors && errors.condition && (
                    <p className="text-xs text-destructive">{errors.condition}</p>
                  )}
                </label>
                <label className="space-y-1 text-sm font-medium">
                  <span>
                    {selectedCategory?.priceLabel ?? 'Price (PKR)'}{' '}
                    <span className="text-destructive">*</span>
                  </span>
                  <input
                    value={details.price}
                    inputMode="decimal"
                    type="number"
                    min={0}
                    aria-invalid={showErrors && Boolean(errors.price)}
                    onChange={(e) => setDetails({ ...details, price: e.target.value })}
                    placeholder="285000"
                    className={inputClass}
                  />
                  {showErrors && errors.price && (
                    <p className="text-xs text-destructive">{errors.price}</p>
                  )}
                </label>
                <div className="space-y-1 text-sm font-medium">
                  <span>Negotiable</span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={details.negotiable}
                    onClick={() => setDetails({ ...details, negotiable: !details.negotiable })}
                    className={cn(
                      'relative flex h-7 w-12 items-center rounded-full transition-colors',
                      details.negotiable ? 'bg-brand' : 'bg-muted-foreground/30',
                    )}
                  >
                    <span
                      className={cn(
                        'absolute h-5 w-5 rounded-full bg-white shadow transition-transform',
                        details.negotiable ? 'translate-x-6' : 'translate-x-1',
                      )}
                    />
                    <span className="sr-only">Price is negotiable</span>
                  </button>
                </div>
                <label className="flex items-start gap-3 text-sm md:col-span-2">
                  <input
                    type="checkbox"
                    checked={details.showPhone}
                    onChange={(e) => setDetails({ ...details, showPhone: e.target.checked })}
                    className="mt-1"
                  />
                  <span>
                    {ur
                      ? 'اس اشتہار پر میرا تصدیق شدہ فون نمبر دکھائیں'
                      : 'Show my verified phone number on this ad'}
                    <small className="mt-1 block text-muted-foreground">
                      {ur
                        ? 'نمبر عوامی ہوگا۔ بند رکھنے پر لوگ پیغام بھیج سکتے ہیں۔'
                        : 'This makes your number public. Keep it off to use website messaging.'}
                    </small>
                  </span>
                </label>
                {details.categoryNodeId && (
                  <p className="text-xs leading-5 text-muted-foreground md:col-span-2">
                    {categoryGuidance(details.categoryNodeId, ur)}
                  </p>
                )}
                {descriptionEditor}
              </div>

              {productDetailsEditor}
            </section>
          )}

          {step === 1 && listingId && (
            <PostAdMediaStep
              listingId={listingId}
              video={video}
              optional={virtual}
              onVideoReady={async (clip) => {
                // Save the video id on the draft straight away, so a closed tab
                // does not lose an uploaded clip.
                const saved = await save('Saving video...', { videoFileId: clip.fileId });
                if (saved) setVideo(clip);
              }}
            />
          )}

          {step === 2 && (
            <PostAdLocationStep
              optionalAddress={virtual}
              value={location}
              onChange={(value) => {
                setLocation(value);
                setDirty(true);
              }}
            />
          )}

          {step === 3 && (
            <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
              <h2 className="text-base font-semibold">Preview & publish</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Check the preview on the right. Publishing runs the AI safety check. Your ad goes
                live for buyers only when every item below is green.
              </p>
              <div className="mt-4">{descriptionEditor}</div>
              {productDetailsEditor}
              <ul className="mt-4 space-y-2">
                {goLiveChecks.map((check) => (
                  <li key={check.label} className="flex items-center gap-2 text-sm">
                    {check.ok ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                    ) : (
                      <XCircle className="h-4 w-4 text-amber-500" aria-hidden="true" />
                    )}
                    {check.label}
                  </li>
                ))}
              </ul>
              {missing.length > 0 && (
                <Alert tone="warning" title="Not ready yet" className="mt-4">
                  {missing.map((m) => MISSING_LABEL[m]).join(' · ')}
                </Alert>
              )}
              {!sellerVerified && (
                <Alert tone="info" title="Ad will stay private for now" className="mt-4">
                  You can publish now; the ad stays private and goes live automatically after your
                  identity, phone, email and profile checks are complete.{' '}
                  <Link href={verifyHref} className="font-medium text-brand underline">
                    Finish verification
                  </Link>
                </Alert>
              )}
              {published && (
                <Alert tone="success" title="Submitted for the safety check" className="mt-4">
                  {sellerVerified
                    ? 'If the check passes, your ad goes live in a minute. Open it to see its status.'
                    : 'Saved. It goes live after verification and the safety check.'}
                </Alert>
              )}
            </section>
          )}

          {/* ── Footer actions ─────────────────────────────────────────── */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={busy !== null || !detailsValid || published}
                onClick={() => void save('Saving draft...')}
              >
                <Save className="mr-2 h-4 w-4" aria-hidden="true" />
                Save draft
              </Button>
              {step > 0 && !published && (
                <Button
                  type="button"
                  variant="outline"
                  disabled={busy !== null}
                  onClick={() => {
                    setError(null);
                    setStep(step - 1);
                  }}
                >
                  <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" />
                  Back
                </Button>
              )}
            </div>
            {step < 3 ? (
              <Button
                type="button"
                size="lg"
                disabled={busy !== null}
                onClick={() => void next()}
                className="bg-brand text-white hover:bg-brand/90"
              >
                {busy ? <Spinner /> : null}
                {busy ??
                  (step === 0
                    ? 'Continue to Photos & Video'
                    : step === 1
                      ? 'Continue to Location'
                      : 'Continue to Preview')}
                {!busy && <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />}
              </Button>
            ) : published ? (
              <Button
                type="button"
                size="lg"
                className="bg-brand text-white hover:bg-brand/90"
                onClick={() => {
                  router.push(`/dashboard/listings/${listingId}`);
                  router.refresh();
                }}
              >
                Open my ad
                <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
              </Button>
            ) : (
              <Button
                type="button"
                size="lg"
                disabled={busy !== null || missing.length > 0 || !detailsValid}
                onClick={() => void publish()}
                className="bg-brand text-white hover:bg-brand/90"
              >
                {busy ? <Spinner /> : <ShieldCheck className="mr-2 h-4 w-4" aria-hidden="true" />}
                {busy ?? 'Publish ad'}
              </Button>
            )}
          </div>
        </div>

        <LivePreview
          details={details}
          location={location}
          imageUrl={images[0]?.thumbnailUrl ?? images[0]?.url ?? null}
          photoCount={images.length}
          hasVideo={Boolean(video)}
          sellerHandle={seller?.handle ?? null}
          trustScore={seller?.score ?? null}
          checks={goLiveChecks}
          analysing={status === 'ANALYSING'}
        />
      </div>
    </div>
  );
}

function LivePreview({
  details,
  location,
  imageUrl,
  photoCount,
  hasVideo,
  sellerHandle,
  trustScore,
  checks,
  analysing,
}: {
  details: DetailsValue;
  location: LocationValue;
  imageUrl: string | null;
  photoCount: number;
  hasVideo: boolean;
  sellerHandle: string | null;
  trustScore: number | null;
  checks: { ok: boolean; label: string }[];
  analysing: boolean;
}) {
  const price = Number(details.price);
  const priceLabel = useMemo(
    () =>
      details.price.trim() && Number.isFinite(price) ? `PKR ${price.toLocaleString()}` : 'PKR -',
    [details.price, price],
  );
  const condition = CONDITIONS.find(([value]) => value === details.condition)?.[1];
  return (
    <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
      <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
        <h2 className="text-base font-semibold">Live preview</h2>
        <div className="mt-3 overflow-hidden rounded-lg border border-border">
          <div className="relative aspect-[4/3] bg-muted">
            {imageUrl ? (
              <Image
                src={imageUrl}
                alt="Main photo preview"
                fill
                className="object-cover"
                unoptimized
              />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Your main photo appears here
              </div>
            )}
            <span className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-white/90 shadow">
              <Heart className="h-4 w-4 text-slate-700" aria-hidden="true" />
            </span>
            {hasVideo && (
              <span className="absolute bottom-2 left-2 inline-flex items-center gap-1 rounded-full bg-black/70 px-2 py-0.5 text-[11px] font-semibold text-white">
                <Play className="h-3 w-3" aria-hidden="true" /> Video
              </span>
            )}
            {photoCount > 1 && (
              <span className="absolute bottom-2 right-2 rounded-full bg-black/60 px-2 py-0.5 text-[11px] font-medium text-white">
                {photoCount} photos
              </span>
            )}
          </div>
          <div className="space-y-1 p-3">
            <p className="text-xl font-bold">{priceLabel}</p>
            <p className="line-clamp-2 text-sm text-foreground">
              {details.title.trim() || 'Your ad title'}
              {condition ? ` · ${condition}` : ''}
            </p>
            <div className="flex items-center justify-between pt-1 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                {location.area
                  ? `${location.area}, ${location.city}`
                  : location.city || 'Area, City'}
              </span>
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" aria-hidden="true" /> Just now
              </span>
            </div>
            <div className="flex items-center justify-between border-t border-border pt-2">
              <span className="text-xs font-medium">
                {sellerHandle ? `@${sellerHandle}` : '@you'}
              </span>
              <span className="rounded-md border border-brand px-2 py-0.5 text-xs font-semibold text-brand">
                Trust {trustScore ?? '-'}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-brand">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h3 className="text-sm font-semibold">Before your ad goes live</h3>
            <p className="text-xs text-muted-foreground">
              AI listing analysis runs when you publish. Buyers only see ads that pass every check.
            </p>
          </div>
        </div>
        <ul className="mt-3 space-y-1.5">
          {checks.map((check) => (
            <li key={check.label} className="flex items-center gap-2 text-xs">
              {check.ok ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
              ) : (
                <span className="h-3.5 w-3.5 rounded-full border-2 border-muted-foreground/40" />
              )}
              <span className={check.ok ? 'text-foreground' : 'text-muted-foreground'}>
                {check.label}
              </span>
            </li>
          ))}
        </ul>
        {analysing && (
          <span className="mt-3 inline-flex items-center gap-1 rounded-full border border-violet-300 bg-violet-50 px-2.5 py-0.5 text-xs font-medium text-violet-700">
            <Clock className="h-3 w-3" aria-hidden="true" /> Safety check running
          </span>
        )}
      </div>
    </aside>
  );
}
