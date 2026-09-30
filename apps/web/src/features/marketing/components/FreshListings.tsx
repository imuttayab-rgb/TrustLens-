'use client';

import { stagger, usePrefersReducedMotion } from '@/lib/motion';
import {
  ListingCard,
  useAddFavorite,
  useFavoriteIds,
  usePublicListings,
  useRemoveFavorite,
} from '@/features/marketplace';
import { useSession } from '@/lib/auth/use-session';
import { Spinner } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

/**
 * Real data, not placeholder cards - the eight most recent active listings,
 * the same public/anonymous read `/browse` itself uses.
 */
export function FreshListings() {
  const t = useTranslations('Home');
  const router = useRouter();
  const reduced = usePrefersReducedMotion();
  const { data: session } = useSession();
  const { data, isPending } = usePublicListings({ sort: 'newest', limit: 8 });
  const { data: favoriteIds } = useFavoriteIds();
  const addFavorite = useAddFavorite();
  const removeFavorite = useRemoveFavorite();

  function toggleFavorite(listingId: string) {
    if (!session) {
      router.push(`/login?next=${encodeURIComponent('/')}`);
      return;
    }
    if (favoriteIds?.has(listingId)) removeFavorite.mutate(listingId);
    else addFavorite.mutate(listingId);
  }

  if (!isPending && (data?.items.length ?? 0) === 0) return null;

  return (
    <section className="mx-auto max-w-7xl px-5 py-10 sm:px-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold tracking-tight sm:text-2xl">{t('freshListings')}</h2>
        <Link
          href="/browse"
          className="text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          {t('viewAll')}
        </Link>
      </div>

      {isPending ? (
        <div className="flex justify-center py-12">
          <Spinner label={t('loadingListings')} />
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {data?.items.map((listing, index) => (
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
      )}
    </section>
  );
}
