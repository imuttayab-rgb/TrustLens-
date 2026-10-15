/** Next.js route/layout composition for (public)/browse: page. */
'use client';

import {
  RecentlyViewedStrip,
  SavedSearchBar,
  useAddFavorite,
  useFavoriteIds,
  usePublicListings,
  useRemoveFavorite,
  type SortOrder,
} from '@/features/marketplace';
import { CategoryFilters, parseFacets } from '@/features/categories';
import { RelatedRecommendations } from '@/features/marketplace';
import { categoryNode, categoryLabel } from '@trustlens/constants';
import { CityPicker } from '@/features/location';
import { askAssistant } from '@/features/assistant';
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
import { Button } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import {
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  Smartphone,
  CircleCheck,
  Grid2x2,
  List,
  Search,
  X,
  SlidersHorizontal,
  Sparkles,
  RotateCcw,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { nextBrowseHref, pageFromParam, priceFromInput, priceRangeError } from './browse-params';

import { BrowseResultCard } from './BrowseResultCard';
import styles from './browse-reference.module.css';

const PAGE_SIZE = 24;

// Default catchment for "Nearby" - wide enough to be useful in a sprawling
// city, narrow enough that "near me" still means something.
const DEFAULT_NEARBY_RADIUS_KM = 15;

const SORT_LABELS: Record<SortOrder, string> = {
  newest: 'Newest',
  relevance: 'Most relevant',
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

function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details open className={styles.filterSection}>
      <summary>
        {title}
        <ChevronDown aria-hidden="true" />
      </summary>
      <div className={styles.filterContent}>{children}</div>
    </details>
  );
}

export default function BrowsePage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const categoryNodeId = categoryNode(searchParams.get('categoryNodeId'))?.id ?? null;
  const facets = parseFacets(searchParams.get('facets'));
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
  const minPrice = priceFromInput(minPriceParam);
  const maxPrice = priceFromInput(maxPriceParam);
  const appliedPriceError = priceRangeError(minPriceParam, maxPriceParam);
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
    sortParam === 'price_asc' || sortParam === 'price_desc' || sortParam === 'relevance'
      ? sortParam
      : 'newest';
  const page = pageFromParam(searchParams.get('page'));
  const view = searchParams.get('view') === 'list' ? 'list' : 'grid';
  const nearLatParam = searchParams.get('lat');
  const nearLngParam = searchParams.get('lng');
  const nearLatitude = nearLatParam ? Number(nearLatParam) : null;
  const nearLongitude = nearLngParam ? Number(nearLngParam) : null;
  const radiusKm =
    nearLatitude !== null ? Number(searchParams.get('radius') ?? DEFAULT_NEARBY_RADIUS_KM) : null;

  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const filterToggle = useRef<HTMLButtonElement>(null);
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
  // A sidebar category click navigates immediately. Keep other unapplied
  // sidebar inputs intact for that navigation; header links/back still sync
  // every draft field from the URL as usual.
  const pendingCategoryClick = useRef<ListingCategory | null | undefined>(undefined);
  useEffect(() => {
    const preserveOtherDrafts =
      pendingCategoryClick.current !== undefined && pendingCategoryClick.current === category;
    pendingCategoryClick.current = undefined;
    if (preserveOtherDrafts) {
      setDraft((current) => ({ ...current, category }));
      return;
    }
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

  const { data, isPending, isError, isFetching, refetch } = usePublicListings({
    category,
    categoryNodeId,
    facets,
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
    router.push(nextBrowseHref(searchParams.toString(), next, resetPage));
  }

  function selectSidebarCategory(nextCategory: ListingCategory | null) {
    if (nextCategory === category) return;
    // Header/home links already write `?category=`. The left rail must do the
    // same instead of waiting for the unrelated "Apply Filters" button.
    pendingCategoryClick.current = nextCategory;
    setDraft((current) => ({ ...current, category: nextCategory }));
    updateParams({ categoryNodeId: null, facets: null, category: nextCategory });
  }

  const draftPriceError = priceRangeError(draft.minPrice, draft.maxPrice);

  function applyDraft() {
    if ((draft.province && !draft.city) || draftPriceError) return;
    if (mobileFiltersOpen) filterToggle.current?.focus();
    setMobileFiltersOpen(false);
    updateParams({
      category: draft.category,
      city: draft.city,
      area: draft.area,
      ...(draft.city !== cityParam || draft.area !== area
        ? { lat: null, lng: null, radius: null }
        : {}),
      minPrice: priceFromInput(draft.minPrice)?.toString() ?? null,
      maxPrice: priceFromInput(draft.maxPrice)?.toString() ?? null,
      condition: draft.condition,
      trust: draft.trustBand,
      verified: draft.verifiedOnly ? '1' : null,
    });
  }

  function clearAll() {
    if (mobileFiltersOpen) filterToggle.current?.focus();
    pendingCategoryClick.current = undefined;
    setDraft({
      category: null,
      minPrice: '',
      maxPrice: '',
      condition: null,
      province: null,
      city: null,
      area: null,
      trustBand: null,
      verifiedOnly: false,
    });
    setMobileFiltersOpen(false);
    setLocationError(null);
    router.push(
      nextBrowseHref('', {
        sort: sort === 'newest' ? null : sort,
        view: view === 'list' ? 'list' : null,
      }),
    );
  }

  function askForHelp() {
    const details = [
      qParam || (category ? LISTING_CATEGORY_LABELS[category] : 'a suitable product'),
      cityParam ? `in ${cityParam}` : '',
      minPrice !== null ? `minimum budget PKR ${minPrice}` : '',
      maxPrice !== null ? `maximum budget PKR ${maxPrice}` : '',
      condition ? `condition: ${CONDITION_LABELS[condition as keyof typeof CONDITION_LABELS]}` : '',
    ]
      .filter(Boolean)
      .join(', ');
    askAssistant(
      `Help me find ${details}. Keep my budget and location constraints. Explain suitable options and distinguish available TrustLens listings from wider market guidance.`,
    );
  }

  function searchNearby() {
    setLocationError(null);
    if (!navigator.geolocation) {
      setLocationError('Your browser does not support location search.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        updateParams({
          lat: String(position.coords.latitude),
          lng: String(position.coords.longitude),
          radius: String(DEFAULT_NEARBY_RADIUS_KM),
        });
      },
      () => {
        setLocationError('Could not get your location - check your browser permissions.');
      },
      { timeout: 10_000 },
    );
  }

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters = Boolean(
    categoryNodeId ||
    Object.keys(facets).length ||
    qParam ||
    category ||
    cityParam ||
    area ||
    minPrice !== null ||
    maxPrice !== null ||
    condition ||
    trustBand ||
    verifiedOnly ||
    nearLatitude !== null,
  );
  const hasSavableFilters = Boolean(
    categoryNodeId ||
    Object.keys(facets).length ||
    qParam ||
    category ||
    cityParam ||
    area ||
    minPrice !== null ||
    maxPrice !== null,
  );

  // What the results count reads as: "Marketplace in DHA, Lahore" once a
  // location is picked, plain "Marketplace" otherwise.
  const locationLabel = area ? `${area}, ${cityParam}` : cityParam;

  const chips: { key: string; label: string; onRemove: () => void }[] = [];
  if (categoryNodeId)
    chips.push({
      key: 'categoryNodeId',
      label: categoryLabel(categoryNodeId),
      onRemove: () => updateParams({ categoryNodeId: null, facets: null }),
    });
  if (Object.keys(facets).length)
    chips.push({
      key: 'facets',
      label: 'Specification filters',
      onRemove: () => updateParams({ facets: null }),
    });
  if (category) {
    chips.push({
      key: 'category',
      label: `Category: ${LISTING_CATEGORY_LABELS[category]}`,
      onRemove: () => updateParams({ categoryNodeId: null, facets: null, category: null }),
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
        updateParams({ q: null });
      },
    });
  }

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.intro}>
          <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
            <Link href="/">Home</Link>
            <span aria-hidden="true">/</span>
            <span>Marketplace</span>
          </nav>
          <h1 className={styles.heading}>
            {locationLabel ? `Marketplace in ${locationLabel}` : 'Marketplace in Pakistan'}
          </h1>
          <p className={styles.subtitle} role="status">
            {isPending
              ? 'Finding listings…'
              : isError || appliedPriceError
                ? 'Find your next purchase on TrustLens'
                : `${total.toLocaleString()} ${verifiedOnly ? 'listings from identity-verified sellers' : total === 1 ? 'listing' : 'listings'}${locationLabel ? ' in your selected location' : nearLatitude !== null ? ' near you' : ' across Pakistan'}`}
          </p>
        </div>
        <button
          ref={filterToggle}
          type="button"
          aria-expanded={mobileFiltersOpen}
          aria-controls="browse-filters"
          onClick={() => setMobileFiltersOpen((open) => !open)}
          className={styles.mobileToggle}
        >
          <SlidersHorizontal aria-hidden="true" />
          {mobileFiltersOpen ? 'Hide filters' : 'Filters'}
          {chips.length > 0 ? ` (${chips.length})` : ''}
        </button>
        <div className={styles.columns}>
          <aside
            id="browse-filters"
            aria-label="Listing filters"
            className={cn(styles.sidebar, mobileFiltersOpen && styles.sidebarOpen)}
          >
            <CategoryFilters
              nodeId={categoryNodeId}
              facets={facets}
              onNavigate={(next) => updateParams(next)}
            />
            {!categoryNodeId && (
              <FilterSection title="Category">
                <div className={styles.categoryControl}>
                  {draft.category === 'mobiles' ? (
                    <Smartphone aria-hidden="true" />
                  ) : (
                    <Grid2x2 aria-hidden="true" />
                  )}
                  <select
                    aria-label="Category"
                    value={draft.category ?? ''}
                    className={cn(styles.input, styles.categorySelect)}
                    onChange={(event) =>
                      selectSidebarCategory((event.target.value || null) as ListingCategory | null)
                    }
                  >
                    <option value="">All categories</option>
                    {LISTING_CATEGORIES.map((slug) => (
                      <option key={slug} value={slug}>
                        {LISTING_CATEGORY_LABELS[slug]}
                      </option>
                    ))}
                  </select>
                  <CircleCheck aria-hidden="true" />
                </div>
              </FilterSection>
            )}
            <FilterSection title="Price Range (PKR)">
              <div className={styles.priceInputs}>
                <input
                  value={draft.minPrice}
                  onChange={(e) => setDraft((d) => ({ ...d, minPrice: e.target.value }))}
                  inputMode="decimal"
                  aria-label="Minimum price in PKR"
                  aria-invalid={Boolean(draftPriceError)}
                  aria-describedby={draftPriceError ? 'price-filter-error' : undefined}
                  placeholder="Min price"
                  className={styles.input ?? ''}
                />
                <span aria-hidden="true">-</span>
                <input
                  value={draft.maxPrice}
                  onChange={(e) => setDraft((d) => ({ ...d, maxPrice: e.target.value }))}
                  inputMode="decimal"
                  aria-label="Maximum price in PKR"
                  aria-invalid={Boolean(draftPriceError)}
                  aria-describedby={draftPriceError ? 'price-filter-error' : undefined}
                  placeholder="Max price"
                  className={styles.input ?? ''}
                />
              </div>
              {draftPriceError && (
                <p id="price-filter-error" role="status" className="mt-2 text-xs text-destructive">
                  {draftPriceError}
                </p>
              )}
            </FilterSection>
            <FilterSection title="Condition">
              <div className={styles.checkList}>
                {LISTING_CONDITIONS.filter(
                  (value) => value !== 'FOR_PARTS' || draft.condition === 'FOR_PARTS',
                ).map((value) => (
                  <label key={value}>
                    <input
                      type="checkbox"
                      checked={draft.condition === value}
                      onChange={() =>
                        setDraft((d) => ({ ...d, condition: d.condition === value ? null : value }))
                      }
                    />
                    {CONDITION_LABELS[value]}
                  </label>
                ))}
              </div>
            </FilterSection>
            <div className={styles.locationRows}>
              <div className={styles.locationRow}>
                <label htmlFor="browse-province">Province</label>
                <select
                  id="browse-province"
                  value={draft.province ?? ''}
                  onChange={(e) =>
                    setDraft((d) => ({
                      ...d,
                      province: e.target.value || null,
                      city: null,
                      area: null,
                    }))
                  }
                  className={styles.input ?? ''}
                >
                  <option value="">All regions</option>
                  {Object.keys(PAKISTAN_PROVINCES)
                    .sort()
                    .map((p) => (
                      <option key={p}>{p}</option>
                    ))}
                </select>
              </div>
              <div className={styles.locationRow}>
                <span>City</span>
                <div className={styles.cityControl}>
                  <CityPicker
                    value={draft.city ?? ''}
                    onChange={(city) =>
                      setDraft((d) => ({
                        ...d,
                        city: city || null,
                        province: d.province || provinceOfCity(city),
                        area: null,
                      }))
                    }
                    cities={citiesInProvince(draft.province)}
                    province={draft.province}
                    placeholder={draft.province ? 'Select city' : 'All cities'}
                    className={styles.input ?? ''}
                  />
                </div>
              </div>
              <div className={styles.locationRow}>
                <label htmlFor="browse-area">Area</label>
                <select
                  id="browse-area"
                  value={draft.area ?? ''}
                  disabled={!draft.city}
                  onChange={(e) => setDraft((d) => ({ ...d, area: e.target.value || null }))}
                  className={styles.input ?? ''}
                >
                  <option value="">All areas</option>
                  {(draft.city ? areasForCity(draft.city) : []).map((a) => (
                    <option key={a}>{a}</option>
                  ))}
                </select>
              </div>
              <div className={styles.locationRow}>
                <label htmlFor="browse-radius">Radius</label>
                <select
                  id="browse-radius"
                  value={nearLatitude !== null ? String(radiusKm) : ''}
                  className={styles.input ?? ''}
                  onChange={(e) => {
                    if (e.target.value === 'nearby') searchNearby();
                    else if (e.target.value === '')
                      updateParams({ lat: null, lng: null, radius: null });
                    else updateParams({ radius: e.target.value });
                  }}
                >
                  <option value="">All distances</option>
                  {nearLatitude !== null ? (
                    [5, 10, 15, 25, 50, 100].map((km) => (
                      <option key={km} value={km}>
                        {km} km
                      </option>
                    ))
                  ) : (
                    <option value="nearby">Use my location</option>
                  )}
                </select>
              </div>
            </div>
            {locationError && (
              <p role="status" className="mb-2 text-xs text-destructive">
                {locationError}
              </p>
            )}
            <FilterSection title="Trust Score">
              <div className={styles.checkList}>
                {TRUST_BANDS.map((band) => (
                  <label key={band.key}>
                    <input
                      type="checkbox"
                      checked={draft.trustBand === band.key}
                      onChange={() =>
                        setDraft((d) => ({
                          ...d,
                          trustBand: d.trustBand === band.key ? null : band.key,
                        }))
                      }
                    />
                    {band.label}
                  </label>
                ))}
              </div>
            </FilterSection>
            <label
              className={styles.verified}
              title="Show listings from sellers whose identity is verified"
            >
              <span>Verified Sellers only</span>
              <input
                type="checkbox"
                aria-label="Identity-verified sellers only"
                checked={draft.verifiedOnly}
                onChange={(e) => setDraft((d) => ({ ...d, verifiedOnly: e.target.checked }))}
              />
            </label>
            {draft.province && !draft.city && (
              <p className={styles.hint} role="status">
                Select a city in {draft.province} to apply the location filter.
              </p>
            )}
            <button
              type="button"
              disabled={Boolean((draft.province && !draft.city) || draftPriceError)}
              onClick={applyDraft}
              className={cn(styles.primary, styles.apply)}
            >
              Apply Filters
            </button>
            <button
              type="button"
              onClick={() => {
                setMobileFiltersOpen(false);
                filterToggle.current?.focus();
              }}
              className={styles.closeFilters}
            >
              Close filters
            </button>
          </aside>
          <div className={styles.resultsColumn}>
            <section className={styles.results} aria-label="Search results" aria-busy={isFetching}>
              {chips.length > 0 && (
                <div className={styles.chips}>
                  {chips.map((chip) => (
                    <button
                      key={chip.key}
                      type="button"
                      onClick={chip.onRemove}
                      aria-label={`Remove ${chip.label} filter`}
                      className={styles.chip}
                    >
                      {chip.label}
                      <X aria-hidden="true" />
                    </button>
                  ))}
                  <button type="button" onClick={clearAll} className={styles.clear}>
                    Clear all
                  </button>
                </div>
              )}
              <div className={styles.toolbar}>
                <h2 className={styles.resultCount} role="status" aria-live="polite">
                  {isPending ? (
                    'Finding listings…'
                  ) : isError || appliedPriceError ? (
                    'Search results'
                  ) : (
                    <>
                      <strong>{total.toLocaleString()}</strong> results
                      {isFetching ? ' · Updating…' : ''}
                    </>
                  )}
                </h2>
                <div className={styles.toolbarActions}>
                  <div className={styles.views} aria-label="Results layout">
                    <button
                      type="button"
                      aria-label="Grid view"
                      aria-pressed={view === 'grid'}
                      onClick={() => updateParams({ view: null }, false)}
                    >
                      <Grid2x2 aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      aria-label="List view"
                      aria-pressed={view === 'list'}
                      onClick={() => updateParams({ view: 'list' }, false)}
                    >
                      <List aria-hidden="true" />
                    </button>
                  </div>
                  <select
                    aria-label="Sort listings"
                    value={sort}
                    onChange={(e) => updateParams({ sort: e.target.value })}
                    className={styles.sort}
                  >
                    {(Object.keys(SORT_LABELS) as SortOrder[]).map((value) => (
                      <option key={value} value={value}>
                        {SORT_LABELS[value]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {appliedPriceError ? (
                <div role="alert" className={styles.empty}>
                  <h3>Check your price range</h3>
                  <p>{appliedPriceError}</p>
                  <Button
                    variant="outline"
                    onClick={() => updateParams({ minPrice: null, maxPrice: null })}
                  >
                    Remove price filter
                  </Button>
                </div>
              ) : isPending ? (
                <div role="status">
                  <span className="sr-only">Loading listings</span>
                  <div
                    aria-hidden="true"
                    className={cn(styles.grid, view === 'list' && styles.list)}
                  >
                    {Array.from({ length: 6 }, (_, i) => (
                      <div
                        key={i}
                        className={cn(
                          styles.card,
                          'motion-safe:animate-pulse',
                          view === 'list' && styles.listCard,
                        )}
                      >
                        <div className={styles.photo} />
                        <div className={styles.cardBody}>
                          <div className={styles.skeletonLine} />
                          <div className={styles.skeletonLine} />
                          <div className={styles.skeletonLine} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : isError ? (
                <div role="alert" className={styles.empty}>
                  <RotateCcw aria-hidden="true" />
                  <h3>We couldn't load these listings</h3>
                  <p>Your filters are still here. Try loading the results again.</p>
                  <Button onClick={() => void refetch()} disabled={isFetching}>
                    {isFetching ? 'Trying again…' : 'Try again'}
                  </Button>
                </div>
              ) : data.items.length === 0 ? (
                <div className={styles.empty}>
                  <Search aria-hidden="true" />
                  <h3>
                    {total > 0 && page > totalPages
                      ? 'This results page is no longer available'
                      : 'No listings found'}
                  </h3>
                  <p>
                    {total > 0 && page > totalPages
                      ? 'Listings may have changed. Return to the first page with your current filters.'
                      : hasFilters
                        ? 'Try a different model, a wider price range or another location.'
                        : 'There are no listings to show yet. Post an ad or ask for buying guidance.'}
                  </p>
                  <div className={styles.emptyActions}>
                    {total > 0 && page > totalPages ? (
                      <Button onClick={() => updateParams({ page: null }, false)}>
                        Go to first page
                      </Button>
                    ) : hasFilters ? (
                      <Button variant="outline" onClick={clearAll}>
                        Clear filters
                      </Button>
                    ) : (
                      <Button asChild variant="outline">
                        <Link href="/dashboard/listings/new">Post an ad</Link>
                      </Button>
                    )}
                    <Button onClick={askForHelp}>
                      <Sparkles className="me-2 h-4 w-4" aria-hidden="true" />
                      Ask for guidance
                    </Button>
                  </div>
                </div>
              ) : (
                <div className={cn(styles.grid, view === 'list' && styles.list)}>
                  {data.items.map((listing) => (
                    <BrowseResultCard
                      key={listing.id}
                      listing={listing}
                      layout={view}
                      favorited={favoriteIds?.has(listing.id) ?? false}
                      onToggleFavorite={() => toggleFavorite(listing.id)}
                      togglingFavorite={
                        (addFavorite.isPending && addFavorite.variables === listing.id) ||
                        (removeFavorite.isPending && removeFavorite.variables === listing.id)
                      }
                    />
                  ))}
                </div>
              )}
            </section>
            {!isPending && !isError && !appliedPriceError && totalPages > 1 && (
              <nav aria-label="Pagination" className={styles.pagination}>
                <button
                  type="button"
                  aria-label="Previous page"
                  disabled={page <= 1}
                  onClick={() => updateParams({ page: String(page - 1) }, false)}
                >
                  <ChevronLeft aria-hidden="true" />
                </button>
                {pageNumbers(page, totalPages).map((entry, index) =>
                  entry === '…' ? (
                    <span key={`ellipsis-${index}`}>…</span>
                  ) : (
                    <button
                      key={entry}
                      type="button"
                      onClick={() =>
                        updateParams({ page: entry === 1 ? null : String(entry) }, false)
                      }
                      aria-current={entry === page ? 'page' : undefined}
                    >
                      {entry}
                    </button>
                  ),
                )}
                <button
                  type="button"
                  aria-label="Next page"
                  disabled={page >= totalPages}
                  onClick={() => updateParams({ page: String(page + 1) }, false)}
                >
                  <ChevronRight aria-hidden="true" />
                </button>
              </nav>
            )}
            {!isPending &&
              !isError &&
              !appliedPriceError &&
              (categoryNodeId || category || qParam) &&
              (page >= totalPages || total === 0) && (
                <RelatedRecommendations
                  category={category}
                  nodeId={categoryNodeId}
                  query={qParam}
                  exclude={data?.items.map((l) => l.id) ?? []}
                />
              )}
          </div>
        </div>
        <details className={styles.extras}>
          <summary>Saved searches, recently viewed &amp; more filters</summary>
          <SavedSearchBar
            hasFilters={hasSavableFilters}
            currentFilters={{
              categoryNodeId,
              facets,
              category,
              q: qParam || null,
              city: cityParam,
              area,
              minPrice,
              maxPrice,
            }}
          />
          <label className="my-4 flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={condition === 'FOR_PARTS'}
              onChange={() =>
                updateParams({ condition: condition === 'FOR_PARTS' ? null : 'FOR_PARTS' })
              }
            />
            For parts / repair
          </label>
          <RecentlyViewedStrip />
        </details>
      </div>
    </div>
  );
}

/** A compact page-number strip with `…` for large gaps - always the first
 * and last page, plus a small window around the current one. */
function pageNumbers(current: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages = new Set<number>([
    1,
    total,
    current,
    current - 1,
    current + 1,
    ...(current <= 3 ? [2, 3, 4, 5] : []),
    ...(current >= total - 2 ? [total - 4, total - 3, total - 2, total - 1] : []),
  ]);
  const sorted = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
  const result: (number | '…')[] = [];
  sorted.forEach((page, index) => {
    if (index > 0 && page - sorted[index - 1]! > 1) result.push('…');
    result.push(page);
  });
  return result;
}
