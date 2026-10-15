/** Reusable UI rendering and interaction component: RelatedRecommendations. */
'use client';
import { useState } from 'react';
import { useLocale } from 'next-intl';
import { useQuery } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { categoryBrowseHref, type ListingCategory } from '@trustlens/constants';
import { profileRequest } from '@/features/profile';
import { useSession } from '@/lib/auth/use-session';
import { useBrowseContext } from '../browse-context';
import { ListingCard } from './ListingCard';
import { useFavoriteIds, useAddFavorite, useRemoveFavorite } from '../hooks/use-favorites';
import type { PublicListing } from '../hooks/use-public-listings';
type Group = {
  key: string;
  categoryNodeId: string | null;
  query: string | null;
  facets: Record<string, string>;
  accessoryBudgetIndependent: boolean;
  items: PublicListing[];
};
const titles: Record<string, [string, string]> = {
  'same-model': ['More of the same model', 'اسی ماڈل کے مزید اشتہارات'],
  'same-family': ['More from this model family', 'اسی ماڈل خاندان کے دیگر اشتہارات'],
  alternatives: ['Similar options to explore', 'ملتے جلتے دیگر انتخاب'],
  'compatible-accessories': [
    'Accessories with seller-stated compatibility',
    'فروخت کنندہ کے مطابق موزوں لوازمات',
  ],
};
export function RelatedRecommendations({
  category,
  nodeId,
  query,
  exclude = [],
  listingId,
}: {
  category: ListingCategory | null;
  nodeId?: string | null;
  model?: string | null;
  query?: string;
  exclude?: string[];
  listingId?: string;
}) {
  const ur = useLocale() === 'ur';
  const context = useBrowseContext();
  const params = useSearchParams();
  const router = useRouter();
  const { data: user } = useSession();
  const [limit, setLimit] = useState(4);
  const request = new URLSearchParams();
  for (const [key, value] of Object.entries({
    listingId,
    categoryNodeId: nodeId,
    category,
    q: query,
    ...context.query,
    minPrice: params.get('minPrice'),
    maxPrice: params.get('maxPrice'),
    exclude: exclude.join(','),
    limit,
  }))
    if (value !== null && value !== undefined && value !== '') request.set(key, String(value));
  const signature = request.toString();
  const result = useQuery<Group[]>({
    queryKey: ['related-recommendations', signature],
    enabled: Boolean(listingId || nodeId || category),
    staleTime: 60000,
    retry: 1,
    queryFn: ({ signal }) => profileRequest(`/public/recommendations?${signature}`, { signal }),
  });
  const { data: favorites } = useFavoriteIds();
  const add = useAddFavorite(),
    remove = useRemoveFavorite();
  const favourite = (id: string) => {
    if (!user)
      router.push(
        `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`,
      );
    else if (favorites?.has(id)) remove.mutate(id);
    else add.mutate(id);
  };
  if (!listingId && !nodeId && !category) return null;
  return (
    <section
      className="mt-8 border-t border-border pt-6"
      aria-label={ur ? 'متعلقہ تجاویز' : 'Related recommendations'}
    >
      {result.isPending ? (
        <p role="status" className="py-5 text-sm text-muted-foreground">
          {ur ? 'متعلقہ اشتہارات لوڈ ہو رہے ہیں…' : 'Finding related listings…'}
        </p>
      ) : result.isError ? (
        <button
          type="button"
          className="rounded-lg border border-border px-4 py-3 text-sm"
          onClick={() => void result.refetch()}
        >
          {ur ? 'متعلقہ اشتہارات دوبارہ لوڈ کریں' : 'Could not load recommendations. Try again.'}
        </button>
      ) : (
        <>
          {result.data?.map((group) => {
            const title = titles[group.key]?.[ur ? 1 : 0] ?? group.key;
            const destination = new URLSearchParams();
            if (group.query) destination.set('q', group.query);
            if (Object.keys(group.facets).length)
              destination.set('facets', JSON.stringify(group.facets));
            if (!group.accessoryBudgetIndependent)
              for (const key of ['minPrice', 'maxPrice']) {
                const value = params.get(key);
                if (value) destination.set(key, value);
              }
            const href = `${group.categoryNodeId ? categoryBrowseHref(group.categoryNodeId) : `/browse?category=${category ?? ''}`}${destination.size ? '&' + destination.toString() : ''}`;
            return (
              <div key={group.key} className="mb-8">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold">{title}</h2>
                  <Link
                    href={context.href(href)}
                    className="text-sm font-semibold text-brand hover:underline"
                  >
                    {ur ? 'مزید دیکھیں' : 'View more'}
                  </Link>
                </div>
                {group.accessoryBudgetIndependent && (
                  <p className="mb-3 text-xs text-muted-foreground">
                    {ur
                      ? 'لوازمات کی قیمتیں الگ ہیں؛ موزونیت خود بھی جانچیں۔'
                      : 'Accessory prices use a separate range. Confirm the fit with the seller.'}
                  </p>
                )}
                <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                  {group.items.map((listing) => (
                    <ListingCard
                      key={listing.id}
                      listing={listing}
                      favorited={favorites?.has(listing.id) ?? false}
                      onToggleFavorite={() => favourite(listing.id)}
                      togglingFavorite={
                        (add.isPending && add.variables === listing.id) ||
                        (remove.isPending && remove.variables === listing.id)
                      }
                    />
                  ))}
                </div>
              </div>
            );
          })}
          {!result.data?.length && (
            <p className="py-5 text-sm text-muted-foreground">
              {ur
                ? 'فی الحال مزید متعلقہ فعال اشتہارات نہیں ملے۔'
                : 'No more related active listings match these filters yet.'}
            </p>
          )}
          {limit < 20 && result.data?.some((g) => g.items.length >= limit) && (
            <button
              type="button"
              onClick={() => setLimit((v) => v + 4)}
              className="rounded-xl border border-border px-5 py-3 text-sm font-semibold"
            >
              {ur ? 'مزید تجاویز دکھائیں' : 'Show more suggestions'}
            </button>
          )}
          {query && (
            <p className="mt-4 text-xs text-muted-foreground">
              {ur
                ? 'یہ تجاویز اوپر کی تلاش کے عین نتائج سے الگ ہیں۔'
                : 'These suggestions are separate from the exact search results above.'}
            </p>
          )}
        </>
      )}
    </section>
  );
}
