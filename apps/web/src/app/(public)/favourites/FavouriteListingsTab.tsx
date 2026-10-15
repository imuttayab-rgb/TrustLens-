/** Next.js route/layout composition for (public)/favourites: FavouriteListingsTab. */
'use client';

import { stagger, usePrefersReducedMotion } from '@/lib/motion';
import {
  ListingCard,
  useAddFavorite,
  useFavoriteIds,
  useMyFavorites,
  useRemoveFavorite,
  type PublicListing,
} from '@/features/marketplace';
import { Alert, Spinner } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { ChevronDown, Columns3, Share2, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { CompareTable } from './CompareTable';

export function FavouriteListingsTab() {
  const reduced = usePrefersReducedMotion();
  const { data, isPending, isError } = useMyFavorites({ limit: 50 });
  const { data: favoriteIds } = useFavoriteIds();
  const addFavorite = useAddFavorite();
  const removeFavorite = useRemoveFavorite();

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [comparing, setComparing] = useState(false);
  const [showUnavailable, setShowUnavailable] = useState(false);
  const [removing, setRemoving] = useState(false);

  if (isPending) {
    return (
      <div className="flex justify-center py-16">
        <Spinner label="Loading your favourites" />
      </div>
    );
  }

  if (isError) {
    return (
      <Alert tone="error" title="Could not load your favourites">
        Try again in a moment.
      </Alert>
    );
  }

  if (data.items.length === 0) {
    return (
      <Alert tone="info" title="No favourites yet">
        Save a listing from Browse to see it here.
      </Alert>
    );
  }

  const available = data.items.filter((l) => l.status === 'ACTIVE');
  const unavailable = data.items.filter((l) => l.status !== 'ACTIVE');
  const selectedListings = data.items.filter((l) => selected.has(l.id));

  function toggleSelected(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleFavorite(listingId: string) {
    if (favoriteIds?.has(listingId)) removeFavorite.mutate(listingId);
    else addFavorite.mutate(listingId);
  }

  async function removeSelected() {
    setRemoving(true);
    try {
      await Promise.all([...selected].map((id) => removeFavorite.mutateAsync(id)));
      setSelected(new Set());
      setComparing(false);
    } finally {
      setRemoving(false);
    }
  }

  async function shareSelected() {
    const lines = selectedListings.map(
      (l) => `${l.title} - ${window.location.origin}/listing/${l.id}`,
    );
    const text = lines.join('\n');
    if (navigator.share) {
      try {
        await navigator.share({ title: 'Listings I saved on TrustLens', text });
      } catch {
        // Cancelled - not an error.
      }
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard access can be denied; no good fallback UI here.
    }
  }

  function renderCard(listing: PublicListing, index: number) {
    return (
      <div key={listing.id} className="relative">
        <div className="absolute -left-2 -top-2 z-10 grid h-6 w-6 place-items-center rounded-full border border-border bg-background shadow-sm">
          <label className="grid cursor-pointer place-items-center">
            <input
              type="checkbox"
              checked={selected.has(listing.id)}
              onClick={(event) => event.stopPropagation()}
              onChange={() => toggleSelected(listing.id)}
              className="h-4 w-4 rounded border-input text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`Select ${listing.title} for comparison`}
            />
          </label>
        </div>
        <div
          style={!reduced ? stagger(index, 45) : undefined}
          className={cn(
            'transition-transform duration-200 hover:-translate-y-1',
            !reduced && 'animate-fade-up',
          )}
        >
          <ListingCard
            listing={listing}
            favorited={favoriteIds?.has(listing.id) ?? true}
            onToggleFavorite={() => toggleFavorite(listing.id)}
            togglingFavorite={
              (addFavorite.isPending && addFavorite.variables === listing.id) ||
              (removeFavorite.isPending && removeFavorite.variables === listing.id)
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <p className="text-sm text-muted-foreground">
          {selected.size > 0 ? `${selected.size} selected` : `${data.items.length} favourites`}
        </p>
        {selected.size > 0 && (
          <div className={cn('flex items-center gap-4 text-sm', !reduced && 'animate-fade-in')}>
            <button
              type="button"
              disabled={selected.size < 2}
              onClick={() => setComparing((c) => !c)}
              className="flex items-center gap-1.5 font-medium text-brand hover:underline disabled:pointer-events-none disabled:opacity-40"
            >
              <Columns3 className="h-4 w-4" aria-hidden="true" />
              Compare
            </button>
            <button
              type="button"
              onClick={() => void shareSelected()}
              className="flex items-center gap-1.5 font-medium text-muted-foreground hover:text-foreground"
            >
              <Share2 className="h-4 w-4" aria-hidden="true" />
              Share Collection
            </button>
            <button
              type="button"
              disabled={removing}
              onClick={() => void removeSelected()}
              className="flex items-center gap-1.5 font-medium text-destructive hover:underline disabled:opacity-60"
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
              Remove Selected
            </button>
          </div>
        )}
      </div>

      {comparing && selectedListings.length >= 2 && (
        <div className="mt-4">
          <CompareTable
            listings={selectedListings}
            onClose={() => setComparing(false)}
            onRemove={(id) => toggleSelected(id)}
          />
        </div>
      )}

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {available.map((listing, index) => renderCard(listing, index))}
      </div>

      {unavailable.length > 0 && (
        <div className="mt-6 border-t border-border pt-4">
          <button
            type="button"
            onClick={() => setShowUnavailable((s) => !s)}
            className="flex w-full items-center justify-between text-left text-sm font-semibold"
          >
            Recently sold or unavailable ({unavailable.length})
            <ChevronDown
              className={cn('h-4 w-4 transition-transform', showUnavailable && 'rotate-180')}
              aria-hidden="true"
            />
          </button>
          {showUnavailable && (
            <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {unavailable.map((listing, index) => renderCard(listing, index))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
