'use client';

import {
  ListingCard,
  RecentlyViewedStrip,
  SavedSearchBar,
  useAddFavorite,
  useFavoriteIds,
  usePublicListings,
  useRemoveFavorite,
  type SortOrder,
} from '@/features/marketplace';
import { useSession } from '@/lib/auth/use-session';
import {
  areasForCity,
  citiesInProvince,
  LISTING_CATEGORIES,
  LISTING_CATEGORY_LABELS,
  PAKISTAN_PROVINCES,
  provinceOfCity,
  type ListingCategory,
} from '@trustlens/constants';
import { LISTING_CONDITIONS } from '@trustlens/validation';
import { Alert, Button, Spinner } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { ChevronRight, Grid2x2, List, Loader2, MapPin, Search, Check, X } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';

const PAGE_SIZE = 24;

// Default catchment for "Nearby" - wide enough to be useful in a sprawling
// city, narrow enough that "near me" still means something.
const DEFAULT_NEARBY_RADIUS_KM = 15;

const SORT_LABELS: Record<SortOrder, string> = {
  newest: 'Newest',
  price_asc: 'Price: low to high',
  price_desc: 'Price: high to low',
};

const CONDITION_LABELS: Record<(typeof LISTING_CONDITIONS)[number], string> = {
  NEW: 'New',
  LIKE_NEW: 'Like New',
  USED: 'Used',
  FOR_PARTS: 'For parts',
};

/** 80+/60-79/below 60 - the same three bands `RISK_PRESENTATION` reads as
 * low/medium/high risk, framed the way a buyer thinks about them here. */
const TRUST_BANDS = [
  { key: 'high', label: '80+ (High Trust)', min: 80, max: null as number | null },
  { key: 'good', label: '60 - 79 (Good)', min: 60, max: 79 },
  { key: 'low', label: 'Below 60', min: null as number | null, max: 59 },
] as const;

interface FilterState {
  category: ListingCategory | null;
  minPrice: string;
  maxPrice: string;
  condition: string | null;
  province: string | null;
  city: string | null;
  area: string | null;
  trustBand: (typeof TRUST_BANDS)[number]['key'] | null;
  verifiedOnly: boolean;
}

function inputClass() {
  return 'h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
}

function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-border/70 py-4 first:pt-0 last:border-0">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}

export default function BrowsePage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const categoryParam = searchParams.get('category');
  const category: ListingCategory | null =
    categoryParam && (LISTING_CATEGORIES as readonly string[]).includes(categoryParam)
      ? (categoryParam as ListingCategory)
      : null;
  const qParam = searchParams.get('q') ?? '';
  const cityParam = searchParams.get('city');
  const areaOptions = cityParam ? areasForCity(cityParam) : [];
  const areaParam = searchParams.get('area');
  const area = areaParam && areaOptions.includes(areaParam) ? areaParam : null;
  const minPriceParam = searchParams.get('minPrice');
  const maxPriceParam = searchParams.get('maxPrice');
  const minPrice = minPriceParam ? Number(minPriceParam) : null;
  const maxPrice = maxPriceParam ? Number(maxPriceParam) : null;
  const conditionParam = searchParams.get('condition');
  const condition =
    conditionParam && (LISTING_CONDITIONS as readonly string[]).includes(conditionParam)
      ? conditionParam
      : null;
  const trustBandParam = searchParams.get('trust');
  const trustBand = TRUST_BANDS.find((b) => b.key === trustBandParam) ?? null;
  const verifiedOnly = searchParams.get('verified') === '1';
  const sortParam = searchParams.get('sort');
  const sort: SortOrder =
    sortParam === 'price_asc' || sortParam === 'price_desc' ? sortParam : 'newest';
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1);
  const view = searchParams.get('view') === 'list' ? 'list' : 'grid';
  const nearLatParam = searchParams.get('lat');
  const nearLngParam = searchParams.get('lng');
  const nearLatitude = nearLatParam ? Number(nearLatParam) : null;
  const nearLongitude = nearLngParam ? Number(nearLngParam) : null;
  const radiusKm =
    nearLatitude !== null ? Number(searchParams.get('radius') ?? DEFAULT_NEARBY_RADIUS_KM) : null;

  const [searchInput, setSearchInput] = useState(qParam);
  useEffect(() => setSearchInput(qParam), [qParam]);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);

  // The sidebar is a draft, committed all at once by "Apply Filters" -
  // matching the reference design, and avoiding a network round trip per
  // checkbox click the way the old immediate-apply sidebar caused.
  const [draft, setDraft] = useState<FilterState>({
    category,
    minPrice: minPriceParam ?? '',
    maxPrice: maxPriceParam ?? '',
    condition,
    province: provinceOfCity(cityParam),
    city: cityParam,
    area,
    trustBand: trustBand?.key ?? null,
    verifiedOnly,
  });
  useEffect(() => {
    setDraft({
      category,
      minPrice: minPriceParam ?? '',
      maxPrice: maxPriceParam ?? '',
      condition,
      province: provinceOfCity(cityParam),
      city: cityParam,
      area,
      trustBand: trustBand?.key ?? null,
      verifiedOnly,
    });
    // Deliberately keyed on `searchParams` alone: this re-syncs the draft
    // from the URL (e.g. a chip removal, browser back/forward), and every
    // other value here is itself derived from `searchParams` - listing them
    // too would just be a no-op re-run of the same effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const { data, isPending, isError } = usePublicListings({
    category,
    q: qParam || null,
    city: cityParam,
    area,
    minPrice,
    maxPrice,
    condition,
    minTrustScore: trustBand?.min ?? null,
    maxTrustScore: trustBand?.max ?? null,
    verifiedOnly,
    nearLatitude,
    nearLongitude,
    radiusKm,
    sort,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });

  const { data: session } = useSession();
  const { data: favoriteIds } = useFavoriteIds();
  const addFavorite = useAddFavorite();
  const removeFavorite = useRemoveFavorite();

  function toggleFavorite(listingId: string) {
    if (!session) {
      const next = `${window.location.pathname}${window.location.search}`;
      router.push(`/login?next=${encodeURIComponent(next)}`);
      return;
    }
    if (favoriteIds?.has(listingId)) removeFavorite.mutate(listingId);
    else addFavorite.mutate(listingId);
  }

  function updateParams(next: Record<string, string | null | undefined>, resetPage = true) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(next)) {
      if (value === undefined) continue;
      if (value) params.set(key, value);
      else params.delete(key);
    }
    if (resetPage) params.delete('page');
    router.push(`/browse${params.toString() ? `?${params.toString()}` : ''}`);
  }

  function applyDraft() {
    updateParams({
      category: draft.category,
      city: draft.city,
      area: draft.city === cityParam ? draft.area : null,
      minPrice: draft.minPrice.trim() || null,
      maxPrice: draft.maxPrice.trim() || null,
      condition: draft.condition,
      trust: draft.trustBand,
      verified: draft.verifiedOnly ? '1' : null,
    });
  }

  function clearAll() {
    router.push('/browse');
  }

  function useNearbySearch() {
    setLocationError(null);
    if (!navigator.geolocation) {
      setLocationError('Your browser does not support location search.');
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        updateParams({
          lat: String(position.coords.latitude),
          lng: String(position.coords.longitude),
          radius: String(DEFAULT_NEARBY_RADIUS_KM),
        });
      },
      () => {
        setLocating(false);
        setLocationError('Could not get your location - check your browser permissions.');
      },
      { timeout: 10_000 },
    );
  }

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters = Boolean(
    qParam ||
    category ||
    cityParam ||
    area ||
    minPrice ||
    maxPrice ||
    condition ||
    trustBand ||
    verifiedOnly ||
    nearLatitude,
  );
  const hasSavableFilters = Boolean(
    qParam || category || cityParam || area || minPrice || maxPrice,
  );

  // What the results count reads as: "Marketplace in DHA, Lahore" once a
  // location is picked, plain "Marketplace" otherwise.
  const locationLabel = area ? `${area}, ${cityParam}` : cityParam;

  const chips: { key: string; label: string; onRemove: () => void }[] = [];
  if (category) {
    chips.push({
      key: 'category',
      label: `Category: ${LISTING_CATEGORY_LABELS[category]}`,
      onRemove: () => updateParams({ category: null }),
    });
  }
  if (area) {
    chips.push({
      key: 'area',
      label: `Area: ${area}`,
      onRemove: () => updateParams({ area: null }),
    });
  } else if (cityParam) {
    chips.push({
      key: 'city',
      label: `City: ${cityParam}`,
      onRemove: () => updateParams({ city: null, area: null }),
    });
  }
  if (nearLatitude !== null) {
    chips.push({
      key: 'radius',
      label: `Radius: ${radiusKm} km`,
      onRemove: () => updateParams({ lat: null, lng: null, radius: null }),
    });
  }
  if (minPrice !== null || maxPrice !== null) {
    chips.push({
      key: 'price',
      label:
        minPrice !== null && maxPrice !== null
          ? `Price: ${minPrice.toLocaleString()} - ${maxPrice.toLocaleString()}`
          : minPrice !== null
            ? `Price: ${minPrice.toLocaleString()}+`
            : `Price: up to ${maxPrice!.toLocaleString()}`,
      onRemove: () => updateParams({ minPrice: null, maxPrice: null }),
    });
  }
  if (condition) {
    chips.push({
      key: 'condition',
      label: `Condition: ${CONDITION_LABELS[condition as keyof typeof CONDITION_LABELS]}`,
      onRemove: () => updateParams({ condition: null }),
    });
  }
  if (trustBand) {
    chips.push({
      key: 'trust',
      label: `Trust Score: ${trustBand.label}`,
      onRemove: () => updateParams({ trust: null }),
    });
  }
  if (verifiedOnly) {
    chips.push({
      key: 'verified',
      label: 'Verified Sellers Only',
      onRemove: () => updateParams({ verified: null }),
    });
  }
  if (qParam) {
    chips.push({
      key: 'q',
      label: `"${qParam}"`,
      onRemove: () => {
        setSearchInput('');
        updateParams({ q: null });
      },
    });
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-1.5 text-sm text-muted-foreground"
      >
        <Link href="/" className="hover:text-foreground hover:underline">
          Home
        </Link>
        <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="text-foreground">Marketplace</span>
      </nav>

      <h1 className="mt-2 text-2xl font-bold sm:text-3xl">
        {locationLabel ? `Marketplace in ${locationLabel}` : 'Marketplace'}
      </h1>
      <p className="mt-1 text-sm text-muted-foreground">
        {isPending ? 'Loading listings…' : `${total.toLocaleString()} verified listings near you`}
      </p>

      <RecentlyViewedStrip />

      <form
        onSubmit={(event) => {
          event.preventDefault();
          updateParams({ q: searchInput.trim() || null });
        }}
        className="mt-6 flex flex-col gap-2 rounded-xl border border-border bg-card p-2 shadow-sm sm:flex-row sm:items-center"
      >
        <div className="flex flex-1 items-center gap-2 px-2">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="What are you looking for?"
            aria-label="Search listings"
            className="h-10 w-full min-w-0 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
        {nearLatitude !== null ? (
          <button
            type="button"
            onClick={() => updateParams({ lat: null, lng: null, radius: null })}
            className="flex h-10 shrink-0 items-center gap-1.5 rounded-md border border-brand bg-brand/10 px-3 text-sm font-medium text-brand"
          >
            <MapPin className="h-4 w-4" aria-hidden="true" />
            Nearby ({radiusKm}km)
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        ) : (
          <button
            type="button"
            onClick={useNearbySearch}
            disabled={locating}
            className="flex h-10 shrink-0 items-center gap-1.5 rounded-md border border-input px-3 text-sm transition-colors hover:border-foreground/40 disabled:opacity-60"
          >
            {locating ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <MapPin className="h-4 w-4" aria-hidden="true" />
            )}
            {locating ? 'Locating…' : 'Nearby'}
          </button>
        )}
        <Button type="submit" className="h-10 shrink-0 gap-2">
          <Search className="h-4 w-4" aria-hidden="true" />
          Search
        </Button>
      </form>
      {locationError && <p className="mt-1 text-xs text-destructive">{locationError}</p>}

      <SavedSearchBar
        hasFilters={hasSavableFilters}
        currentFilters={{ category, q: qParam || null, city: cityParam, area, minPrice, maxPrice }}
      />

      {chips.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {chips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              onClick={chip.onRemove}
              className="flex items-center gap-1.5 rounded-full border border-brand/30 bg-brand/10 px-3 py-1 text-xs font-medium text-brand transition-colors hover:bg-brand/15"
            >
              {chip.label}
              <X className="h-3 w-3" aria-hidden="true" />
            </button>
          ))}
          <button
            type="button"
            onClick={clearAll}
            className="text-xs font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Clear all
          </button>
        </div>
      )}

      <div className="mt-6 grid gap-8 lg:grid-cols-[240px_1fr]">
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <FilterSection title="Category">
            <ul className="space-y-1">
              <li>
                <button
                  type="button"
                  onClick={() => setDraft((d) => ({ ...d, category: null }))}
                  className={cn(
                    'flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-left text-sm transition-colors',
                    draft.category === null
                      ? 'bg-brand/10 font-medium text-brand'
                      : 'text-muted-foreground hover:bg-muted',
                  )}
                >
                  All categories
                  {draft.category === null && <Check className="h-4 w-4" aria-hidden="true" />}
                </button>
              </li>
              {LISTING_CATEGORIES.map((slug) => (
                <li key={slug}>
                  <button
                    type="button"
                    onClick={() =>
                      setDraft((d) => ({ ...d, category: d.category === slug ? null : slug }))
                    }
                    className={cn(
                      'flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-left text-sm transition-colors',
                      draft.category === slug
                        ? 'bg-brand/10 font-medium text-brand'
                        : 'text-muted-foreground hover:bg-muted',
                    )}
                  >
                    {LISTING_CATEGORY_LABELS[slug]}
                    {draft.category === slug && (
                      <Check className="h-4 w-4 shrink-0" aria-hidden="true" />
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </FilterSection>

          <FilterSection title="Price Range (PKR)">
            <div className="flex items-center gap-2">
              <input
                value={draft.minPrice}
                onChange={(event) => setDraft((d) => ({ ...d, minPrice: event.target.value }))}
                inputMode="numeric"
                placeholder="Min price"
                className={inputClass()}
              />
              <span className="text-muted-foreground">-</span>
              <input
                value={draft.maxPrice}
                onChange={(event) => setDraft((d) => ({ ...d, maxPrice: event.target.value }))}
                inputMode="numeric"
                placeholder="Max price"
                className={inputClass()}
              />
            </div>
          </FilterSection>

          <FilterSection title="Condition">
            <ul className="space-y-2">
              {LISTING_CONDITIONS.map((value) => (
                <li key={value}>
                  <label className="flex cursor-pointer items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={draft.condition === value}
                      onChange={() =>
                        setDraft((d) => ({
                          ...d,
                          condition: d.condition === value ? null : value,
                        }))
                      }
                      className="h-4 w-4 rounded border-input text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                    {CONDITION_LABELS[value]}
                  </label>
                </li>
              ))}
            </ul>
          </FilterSection>

          <FilterSection title="Province">
            <select
              value={draft.province ?? ''}
              onChange={(event) => {
                const province = event.target.value || null;
                setDraft((d) => ({ ...d, province, city: null, area: null }));
              }}
              className={inputClass()}
            >
              <option value="">All provinces</option>
              {Object.keys(PAKISTAN_PROVINCES).map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </FilterSection>

          <FilterSection title="City">
            <select
              value={draft.city ?? ''}
              onChange={(event) =>
                setDraft((d) => ({ ...d, city: event.target.value || null, area: null }))
              }
              className={inputClass()}
            >
              <option value="">All cities</option>
              {citiesInProvince(draft.province).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </FilterSection>

          <FilterSection title="Area">
            <select
              value={draft.city === cityParam ? (draft.area ?? '') : ''}
              disabled={!draft.city}
              onChange={(event) => setDraft((d) => ({ ...d, area: event.target.value || null }))}
              className={cn(inputClass(), 'disabled:opacity-50')}
            >
              <option value="">{draft.city ? 'All areas' : 'Choose a city first'}</option>
              {(draft.city ? areasForCity(draft.city) : []).map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </FilterSection>

          {nearLatitude !== null && (
            <FilterSection title="Radius">
              <select
                value={String(radiusKm)}
                onChange={(event) => updateParams({ radius: event.target.value })}
                className={inputClass()}
              >
                {[5, 10, 15, 25, 50, 100].map((km) => (
                  <option key={km} value={km}>
                    {km} km
                  </option>
                ))}
              </select>
            </FilterSection>
          )}

          <FilterSection title="Trust Score">
            <ul className="space-y-2">
              {TRUST_BANDS.map((band) => (
                <li key={band.key}>
                  <label className="flex cursor-pointer items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={draft.trustBand === band.key}
                      onChange={() =>
                        setDraft((d) => ({
                          ...d,
                          trustBand: d.trustBand === band.key ? null : band.key,
                        }))
                      }
                      className="h-4 w-4 rounded border-input text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                    {band.label}
                  </label>
                </li>
              ))}
            </ul>
          </FilterSection>

          <FilterSection title="Verified Sellers only">
            <label className="flex cursor-pointer items-center justify-between text-sm">
              <span className="text-muted-foreground">Identity-verified sellers only</span>
              <input
                type="checkbox"
                checked={draft.verifiedOnly}
                onChange={(event) =>
                  setDraft((d) => ({ ...d, verifiedOnly: event.target.checked }))
                }
                className="h-4 w-4 rounded border-input text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
          </FilterSection>

          <Button onClick={applyDraft} className="mt-4 w-full">
            Apply Filters
          </Button>
        </aside>

        <section className="min-w-0">
          {isPending ? (
            <div className="flex justify-center py-16">
              <Spinner label="Loading listings" />
            </div>
          ) : isError ? (
            <Alert tone="error" title="Could not load listings">
              Try again in a moment.
            </Alert>
          ) : data.items.length === 0 ? (
            <Alert tone="info" title="No listings found">
              {hasFilters
                ? 'Try a different search, area, or price range.'
                : 'Nobody has listed anything yet.'}
            </Alert>
          ) : (
            <>
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-muted-foreground">
                  {total.toLocaleString()} result{total === 1 ? '' : 's'}
                </p>
                <div className="flex items-center gap-2">
                  <div className="flex overflow-hidden rounded-md border border-input">
                    <button
                      type="button"
                      aria-label="Grid view"
                      aria-pressed={view === 'grid'}
                      onClick={() => updateParams({ view: null }, false)}
                      className={cn(
                        'grid h-9 w-9 place-items-center transition-colors',
                        view === 'grid'
                          ? 'bg-brand text-[hsl(var(--background))]'
                          : 'text-muted-foreground hover:bg-muted',
                      )}
                    >
                      <Grid2x2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      aria-label="List view"
                      aria-pressed={view === 'list'}
                      onClick={() => updateParams({ view: 'list' }, false)}
                      className={cn(
                        'grid h-9 w-9 place-items-center border-l border-input transition-colors',
                        view === 'list'
                          ? 'bg-brand text-[hsl(var(--background))]'
                          : 'text-muted-foreground hover:bg-muted',
                      )}
                    >
                      <List className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                  <select
                    value={sort}
                    onChange={(event) => updateParams({ sort: event.target.value }, false)}
                    className="h-9 rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {(Object.keys(SORT_LABELS) as SortOrder[]).map((value) => (
                      <option key={value} value={value}>
                        {SORT_LABELS[value]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div
                className={cn(
                  'mt-4 grid gap-4',
                  view === 'list' ? 'grid-cols-1' : 'grid-cols-2 sm:grid-cols-3',
                )}
              >
                {data.items.map((listing) => (
                  <div key={listing.id} className={view === 'list' ? 'max-w-md' : undefined}>
                    <ListingCard
                      listing={listing}
                      favorited={favoriteIds?.has(listing.id) ?? false}
                      onToggleFavorite={() => toggleFavorite(listing.id)}
                      togglingFavorite={
                        (addFavorite.isPending && addFavorite.variables === listing.id) ||
                        (removeFavorite.isPending && removeFavorite.variables === listing.id)
                      }
                    />
                  </div>
                ))}
              </div>

              {totalPages > 1 && (
                <nav
                  aria-label="Pagination"
                  className="mt-8 flex items-center justify-center gap-1.5"
                >
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => updateParams({ page: String(page - 1) }, false)}
                    className="rounded-md border border-border px-2.5 py-1.5 text-sm disabled:pointer-events-none disabled:opacity-40"
                  >
                    ‹
                  </button>
                  {pageNumbers(page, totalPages).map((entry, index) =>
                    entry === '…' ? (
                      <span
                        key={`ellipsis-${index}`}
                        className="px-1 text-sm text-muted-foreground"
                      >
                        …
                      </span>
                    ) : (
                      <button
                        key={entry}
                        type="button"
                        onClick={() =>
                          updateParams({ page: entry === 1 ? null : String(entry) }, false)
                        }
                        aria-current={entry === page ? 'page' : undefined}
                        className={cn(
                          'h-8 w-8 rounded-md text-sm transition-colors',
                          entry === page
                            ? 'bg-brand text-[hsl(var(--background))]'
                            : 'text-muted-foreground hover:bg-muted',
                        )}
                      >
                        {entry}
                      </button>
                    ),
                  )}
                  <button
                    type="button"
                    disabled={page >= totalPages}
                    onClick={() => updateParams({ page: String(page + 1) }, false)}
                    className="rounded-md border border-border px-2.5 py-1.5 text-sm disabled:pointer-events-none disabled:opacity-40"
                  >
                    ›
                  </button>
                </nav>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}

/** A compact page-number strip with `…` for large gaps - always the first
 * and last page, plus a small window around the current one. */
function pageNumbers(current: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages = new Set<number>([1, total, current, current - 1, current + 1]);
  const sorted = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
  const result: (number | '…')[] = [];
  sorted.forEach((page, index) => {
    if (index > 0 && page - sorted[index - 1]! > 1) result.push('…');
    result.push(page);
  });
  return result;
}
