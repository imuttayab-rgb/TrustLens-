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
  LISTING_CATEGORIES,
  LISTING_CATEGORY_LABELS,
  PAKISTAN_CITIES,
  type ListingCategory,
} from '@trustlens/constants';
import { Alert, Spinner } from '@trustlens/ui';
import { MapPin, Search } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';

const PAGE_SIZE = 24;

// Default catchment for "Nearby" - wide enough to be useful in a sprawling
// city, narrow enough that "near me" still means something.
const DEFAULT_NEARBY_RADIUS_KM = 15;

const SORT_LABELS: Record<SortOrder, string> = {
  newest: 'Newest first',
  price_asc: 'Price: low to high',
  price_desc: 'Price: high to low',
};

function selectClass() {
  return 'h-10 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
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
  const city =
    cityParam && (PAKISTAN_CITIES as readonly string[]).includes(cityParam) ? cityParam : null;
  const areaOptions = city ? areasForCity(city) : [];
  const areaParam = searchParams.get('area');
  const area = areaParam && areaOptions.includes(areaParam) ? areaParam : null;
  const minPriceParam = searchParams.get('minPrice');
  const maxPriceParam = searchParams.get('maxPrice');
  const minPrice = minPriceParam ? Number(minPriceParam) : null;
  const maxPrice = maxPriceParam ? Number(maxPriceParam) : null;
  const sortParam = searchParams.get('sort');
  const sort: SortOrder =
    sortParam === 'price_asc' || sortParam === 'price_desc' ? sortParam : 'newest';
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1);
  const attributeKey = searchParams.get('attr') || null;
  const attributeValue = searchParams.get('attrValue') || null;
  const nearLatParam = searchParams.get('lat');
  const nearLngParam = searchParams.get('lng');
  const nearLatitude = nearLatParam ? Number(nearLatParam) : null;
  const nearLongitude = nearLngParam ? Number(nearLngParam) : null;
  const radiusKm =
    nearLatitude !== null ? Number(searchParams.get('radius') ?? DEFAULT_NEARBY_RADIUS_KM) : null;

  // Local input state so typing doesn't refetch on every keystroke - only
  // once the seller stops for a moment, or presses Enter.
  const [searchInput, setSearchInput] = useState(qParam);
  useEffect(() => setSearchInput(qParam), [qParam]);
  const [minPriceInput, setMinPriceInput] = useState(minPriceParam ?? '');
  const [maxPriceInput, setMaxPriceInput] = useState(maxPriceParam ?? '');
  useEffect(() => setMinPriceInput(minPriceParam ?? ''), [minPriceParam]);
  useEffect(() => setMaxPriceInput(maxPriceParam ?? ''), [maxPriceParam]);
  const [attrKeyInput, setAttrKeyInput] = useState(attributeKey ?? '');
  const [attrValueInput, setAttrValueInput] = useState(attributeValue ?? '');
  useEffect(() => setAttrKeyInput(attributeKey ?? ''), [attributeKey]);
  useEffect(() => setAttrValueInput(attributeValue ?? ''), [attributeValue]);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);

  const { data, isPending, isError } = usePublicListings({
    category,
    q: qParam || null,
    city,
    area,
    minPrice,
    maxPrice,
    attributeKey,
    attributeValue,
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
    if (favoriteIds?.has(listingId)) {
      removeFavorite.mutate(listingId);
    } else {
      addFavorite.mutate(listingId);
    }
  }

  function updateParams(next: {
    category?: string | null;
    q?: string | null;
    city?: string | null;
    area?: string | null;
    minPrice?: string | null;
    maxPrice?: string | null;
    attr?: string | null;
    attrValue?: string | null;
    lat?: string | null;
    lng?: string | null;
    radius?: string | null;
    sort?: string | null;
    page?: number;
  }) {
    const params = new URLSearchParams(searchParams.toString());
    const setOrDelete = (key: string, value: string | null | undefined) => {
      if (value === undefined) return;
      if (value) params.set(key, value);
      else params.delete(key);
    };
    setOrDelete('category', next.category);
    setOrDelete('q', next.q);
    setOrDelete('city', next.city);
    // Changing the city invalidates whatever area was picked under the old one.
    if (next.city !== undefined) params.delete('area');
    setOrDelete('area', next.area);
    setOrDelete('minPrice', next.minPrice);
    setOrDelete('maxPrice', next.maxPrice);
    setOrDelete('attr', next.attr);
    setOrDelete('attrValue', next.attrValue);
    setOrDelete('lat', next.lat);
    setOrDelete('lng', next.lng);
    setOrDelete('radius', next.radius);
    setOrDelete('sort', next.sort === 'newest' ? null : next.sort);
    if (next.page !== undefined && next.page > 1) params.set('page', String(next.page));
    else params.delete('page');
    router.push(`/browse${params.toString() ? `?${params.toString()}` : ''}`);
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
    qParam || category || city || area || minPrice || maxPrice || attributeKey || nearLatitude,
  );
  // Only the fields a saved search can actually reproduce - not the
  // attribute/nearby filters, which SavedSearch doesn't carry.
  const hasSavableFilters = Boolean(qParam || category || city || area || minPrice || maxPrice);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
      <h1 className="text-2xl font-bold sm:text-3xl">Browse listings</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Everything shown here has passed TrustLens&apos;s scam-pattern check.
      </p>

      <RecentlyViewedStrip />

      <form
        onSubmit={(event) => {
          event.preventDefault();
          updateParams({ q: searchInput.trim() });
        }}
        className="mt-6 flex gap-2"
      >
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search listings…"
            aria-label="Search listings"
            className="h-11 w-full rounded-md border border-input bg-background pl-9 pr-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-sm"
          />
        </div>
        {nearLatitude !== null ? (
          <button
            type="button"
            onClick={() => updateParams({ lat: null, lng: null, radius: null })}
            className="flex h-11 items-center gap-1.5 rounded-md border border-foreground bg-foreground px-3 text-sm text-background"
          >
            <MapPin className="h-4 w-4" aria-hidden="true" />
            Nearby ({radiusKm}km)
          </button>
        ) : (
          <button
            type="button"
            onClick={useNearbySearch}
            disabled={locating}
            className="flex h-11 items-center gap-1.5 rounded-md border border-input px-3 text-sm hover:border-foreground/50 disabled:opacity-60"
          >
            <MapPin className="h-4 w-4" aria-hidden="true" />
            {locating ? 'Locating…' : 'Nearby'}
          </button>
        )}
      </form>
      {locationError && <p className="mt-1 text-xs text-destructive">{locationError}</p>}

      <SavedSearchBar
        hasFilters={hasSavableFilters}
        currentFilters={{ category, q: qParam || null, city, area, minPrice, maxPrice }}
      />

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => updateParams({ category: null })}
          className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
            category === null
              ? 'border-foreground bg-foreground text-background'
              : 'border-border text-muted-foreground hover:border-foreground/50 hover:text-foreground'
          }`}
        >
          All categories
        </button>
        {LISTING_CATEGORIES.map((slug) => (
          <button
            key={slug}
            type="button"
            onClick={() => updateParams({ category: slug })}
            className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
              category === slug
                ? 'border-foreground bg-foreground text-background'
                : 'border-border text-muted-foreground hover:border-foreground/50 hover:text-foreground'
            }`}
          >
            {LISTING_CATEGORY_LABELS[slug]}
          </button>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-border/60 pt-4">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          City
          <select
            value={city ?? ''}
            onChange={(event) => updateParams({ city: event.target.value || null })}
            className={selectClass()}
          >
            <option value="">All cities</option>
            {PAKISTAN_CITIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Area
          <select
            value={area ?? ''}
            disabled={!city}
            onChange={(event) => updateParams({ area: event.target.value || null })}
            className={`${selectClass()} disabled:opacity-50`}
          >
            <option value="">{city ? 'All areas' : 'Choose a city first'}</option>
            {areaOptions.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Min price
          <input
            value={minPriceInput}
            onChange={(event) => setMinPriceInput(event.target.value)}
            onBlur={() => updateParams({ minPrice: minPriceInput.trim() || null })}
            inputMode="numeric"
            placeholder="0"
            className={`${selectClass()} w-28`}
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Max price
          <input
            value={maxPriceInput}
            onChange={(event) => setMaxPriceInput(event.target.value)}
            onBlur={() => updateParams({ maxPrice: maxPriceInput.trim() || null })}
            inputMode="numeric"
            placeholder="Any"
            className={`${selectClass()} w-28`}
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Spec name
          <input
            value={attrKeyInput}
            onChange={(event) => setAttrKeyInput(event.target.value)}
            onBlur={() => updateParams({ attr: attrKeyInput.trim() || null })}
            placeholder="e.g. storage"
            className={`${selectClass()} w-32`}
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Spec value
          <input
            value={attrValueInput}
            onChange={(event) => setAttrValueInput(event.target.value)}
            onBlur={() => updateParams({ attrValue: attrValueInput.trim() || null })}
            placeholder="e.g. 128GB"
            disabled={!attrKeyInput.trim()}
            className={`${selectClass()} w-32 disabled:opacity-50`}
          />
        </label>

        {nearLatitude !== null && (
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Radius
            <select
              value={String(radiusKm)}
              onChange={(event) => updateParams({ radius: event.target.value })}
              className={selectClass()}
            >
              {[5, 10, 15, 25, 50, 100].map((km) => (
                <option key={km} value={km}>
                  {km} km
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="ml-auto flex flex-col gap-1 text-xs text-muted-foreground">
          Sort by
          <select
            value={sort}
            onChange={(event) => updateParams({ sort: event.target.value })}
            className={selectClass()}
          >
            {(Object.keys(SORT_LABELS) as SortOrder[]).map((value) => (
              <option key={value} value={value}>
                {SORT_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-8">
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
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {data.items.map((listing) => (
                <ListingCard
                  key={listing.id}
                  listing={listing}
                  favorited={favoriteIds?.has(listing.id) ?? false}
                  onToggleFavorite={() => toggleFavorite(listing.id)}
                  togglingFavorite={
                    (addFavorite.isPending && addFavorite.variables === listing.id) ||
                    (removeFavorite.isPending && removeFavorite.variables === listing.id)
                  }
                />
              ))}
            </div>

            {totalPages > 1 && (
              <div className="mt-8 flex items-center justify-center gap-4">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => updateParams({ page: page - 1 })}
                  className="rounded-md border border-border px-3 py-1.5 text-sm disabled:pointer-events-none disabled:opacity-40"
                >
                  Previous
                </button>
                <span className="text-sm text-muted-foreground">
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => updateParams({ page: page + 1 })}
                  className="rounded-md border border-border px-3 py-1.5 text-sm disabled:pointer-events-none disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
