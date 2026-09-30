'use client';

import { ListingCard } from './ListingCard';
import { useAddFavorite, useFavoriteIds, useRemoveFavorite } from '../hooks/use-favorites';
import { usePublicListings } from '../hooks/use-public-listings';
import { useSession } from '@/lib/auth/use-session';
import { stagger, usePrefersReducedMotion } from '@/lib/motion';
import { type ListingCategory } from '@trustlens/constants';
import { cn } from '@trustlens/utils';
import { ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

/** Same category, same public catalog search Browse and the homepage use -
 * no separate "similar" model, just a category filter with this listing
 * excluded from its own recommendations. */
export function SimilarListings({
  category,
  excludeListingId,
}: {
  category: ListingCategory | null;
  excludeListingId: string;
}) {
  const reduced = usePrefersReducedMotion();
  const router = useRouter();
  const { data: session } = useSession();
  const { data, isPending } = usePublicListings({ category, sort: 'newest', limit: 8 });
  const { data: favoriteIds } = useFavoriteIds();
  const addFavorite = useAddFavorite();
  const removeFavorite = useRemoveFavorite();

  const similar = (data?.items ?? []).filter((l) => l.id !== excludeListingId).slice(0, 4);

  function toggleFavorite(listingId: string) {
    if (!session) {
      router.push(`/login?next=${encodeURIComponent(window.location.pathname)}`);
      return;
    }
    if (favoriteIds?.has(listingId)) removeFavorite.mutate(listingId);
    else addFavorite.mutate(listingId);
  }

  if (!isPending && similar.length === 0) return null;

  return (
    <section className="mt-10 border-t border-border pt-8">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">Similar verified listings</h2>
        {category && (
          <Link
            href={`/browse?category=${category}`}
            className="flex items-center gap-0.5 text-sm font-medium text-brand hover:underline"
          >
            View all
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {similar.map((listing, index) => (
          <div
            key={listing.id}
            style={!reduced ? stagger(index, 60) : undefined}
            className={cn(
              'transition-transform duration-200 hover:-translate-y-1',
              !reduced && 'animate-fade-up',
            )}
          >
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
    </section>
  );
}
