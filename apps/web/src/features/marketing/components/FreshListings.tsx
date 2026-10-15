/** Reusable UI rendering and interaction component: FreshListings. */
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
import { ArrowRight, PackageOpen } from 'lucide-react';
import { cn } from '@trustlens/utils';
import { useTranslations, useLocale } from 'next-intl';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

/**
 * Real data, not placeholder cards - the eight most recent active listings,
 * the same public/anonymous read `/browse` itself uses.
 */
export function FreshListings() {
  const t = useTranslations('Home');
  const ur = useLocale() === 'ur';
  const router = useRouter();
  const reduced = usePrefersReducedMotion();
  const { data: session } = useSession();
  const { data, isPending, isError, refetch } = usePublicListings({ sort: 'newest', limit: 8 });
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

  return (
    <section className="mx-auto max-w-7xl px-5 py-10 sm:px-8">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-brand">
            {ur ? 'تازہ اشتہارات' : 'Fresh on TrustLens'}
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
            {ur ? 'آپ کی اگلی اچھی تلاش۔' : 'Your next good find.'}
          </h2>
        </div>
        <Link
          href="/browse"
          className="text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          {t('viewAll')} <ArrowRight className="ms-1 inline h-3.5 w-3.5 rtl:rotate-180" />
        </Link>
      </div>

      {isPending ? (
        <div className="flex justify-center py-12">
          <Spinner label={t('loadingListings')} />
        </div>
      ) : isError ? (
        <div className="mt-6 rounded-2xl border border-dashed border-border p-8 text-center">
          <p className="text-sm text-muted-foreground">
            {ur ? 'اشتہارات لوڈ نہیں ہو سکے۔' : 'We couldn’t load the latest listings.'}
          </p>
          <button
            type="button"
            onClick={() => void refetch()}
            className="mt-3 text-sm font-semibold text-brand"
          >
            {ur ? 'دوبارہ کوشش کریں' : 'Try again'}
          </button>
        </div>
      ) : !data?.items.length ? (
        <div className="mt-6 flex flex-col items-center rounded-2xl border border-dashed border-border bg-muted/20 px-6 py-10 text-center">
          <PackageOpen className="h-9 w-9 text-brand/70" strokeWidth={1.3} />
          <h3 className="mt-4 text-base font-semibold">
            {ur ? 'اگلی اچھی تلاش آپ کی ہو سکتی ہے۔' : 'The next good find could be yours.'}
          </h3>
          <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
            {ur
              ? 'ابھی کوئی فعال اشتہار موجود نہیں۔ اپنی چیز پوسٹ کر کے آغاز کریں۔'
              : 'No active listings yet. Give something you no longer need a new home.'}
          </p>
          <Link
            href="/dashboard/listings/new"
            className="mt-5 rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground"
          >
            {ur ? 'اشتہار پوسٹ کریں' : 'Post an ad'}
          </Link>
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
