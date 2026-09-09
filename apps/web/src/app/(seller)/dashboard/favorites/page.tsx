'use client';

import {
  ListingCard,
  useMyFavorites,
  useRemoveFavorite,
  type PublicListing,
} from '@/features/marketplace';
import { Alert, Spinner } from '@trustlens/ui';

export default function FavoritesPage() {
  const { data, isPending, isError } = useMyFavorites({ limit: 50 });
  const removeFavorite = useRemoveFavorite();

  return (
    <div>
      <h1 className="text-2xl font-bold">Your favorites</h1>
      <p className="mt-1 text-sm text-muted-foreground">Listings you&apos;ve saved from Browse.</p>

      <div className="mt-8">
        {isPending ? (
          <div className="flex justify-center py-16">
            <Spinner label="Loading your favorites" />
          </div>
        ) : isError ? (
          <Alert tone="error" title="Could not load your favorites">
            Try again in a moment.
          </Alert>
        ) : data.items.length === 0 ? (
          <Alert tone="info" title="No favorites yet">
            Save a listing from Browse to see it here.
          </Alert>
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {data.items.map((listing: PublicListing) => (
              <ListingCard
                key={listing.id}
                listing={listing}
                favorited
                onToggleFavorite={() => removeFavorite.mutate(listing.id)}
                togglingFavorite={
                  removeFavorite.isPending && removeFavorite.variables === listing.id
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
