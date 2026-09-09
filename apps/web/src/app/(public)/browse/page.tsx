'use client';

import {
  ListingCard,
  useAddFavorite,
  useFavoriteIds,
  usePublicListings,
  useRemoveFavorite,
} from '@/features/marketplace';
import { useSession } from '@/lib/auth/use-session';
import {
  LISTING_CATEGORIES,
  LISTING_CATEGORY_LABELS,
  type ListingCategory,
} from '@trustlens/constants';
import { Alert, Spinner } from '@trustlens/ui';
import { Search } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';

const PAGE_SIZE = 24;

export default function BrowsePage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const categoryParam = searchParams.get('category');
  const category: ListingCategory | null =
    categoryParam && (LISTING_CATEGORIES as readonly string[]).includes(categoryParam)
      ? (categoryParam as ListingCategory)
      : null;
  const qParam = searchParams.get('q') ?? '';
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1);

  // Local input state so typing doesn't refetch on every keystroke - only
  // once the seller stops for a moment, or presses Enter.
  const [searchInput, setSearchInput] = useState(qParam);
  useEffect(() => setSearchInput(qParam), [qParam]);

  const { data, isPending, isError } = usePublicListings({
    category,
    q: qParam || null,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });

  const { data: session } = useSession();
  const { data: favoriteIds } = useFavoriteIds();
  const addFavorite = useAddFavorite();
  const removeFavorite = useRemoveFavorite();

  function toggleFavorite(listingId: string) {
    if (!session) {
      router.push('/login');
      return;
    }
    if (favoriteIds?.has(listingId)) {
      removeFavorite.mutate(listingId);
    } else {
      addFavorite.mutate(listingId);
    }
  }

  function updateParams(next: { category?: string | null; q?: string | null; page?: number }) {
    const params = new URLSearchParams(searchParams.toString());
    if (next.category !== undefined) {
      if (next.category) params.set('category', next.category);
      else params.delete('category');
    }
    if (next.q !== undefined) {
      if (next.q) params.set('q', next.q);
      else params.delete('q');
    }
    if (next.page !== undefined) {
      if (next.page > 1) params.set('page', String(next.page));
      else params.delete('page');
    } else {
      params.delete('page');
    }
    router.push(`/browse${params.toString() ? `?${params.toString()}` : ''}`);
  }

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
      <h1 className="text-2xl font-bold sm:text-3xl">Browse listings</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Everything shown here has passed TrustLens&apos;s scam-pattern check.
      </p>

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
      </form>

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
            {qParam || category
              ? 'Try a different search or category.'
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
