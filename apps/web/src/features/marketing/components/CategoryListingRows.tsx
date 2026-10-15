/** Reusable UI rendering and interaction component: CategoryListingRows. */
'use client';
import { useEffect, useRef, useState } from 'react';
import { useLocale } from 'next-intl';
import Link from 'next/link';
import { useBrowseContext } from '@/features/marketplace';
import { useRouter } from 'next/navigation';
import {
  MARKETPLACE_ROOTS,
  categoryBrowseHref,
  categoryLabel,
  type ListingCategory,
} from '@trustlens/constants';
import { useSession } from '@/lib/auth/use-session';
import {
  ListingCard,
  usePublicListings,
  useFavoriteIds,
  useAddFavorite,
  useRemoveFavorite,
} from '@/features/marketplace';
export function ListingRow({
  nodeId,
  category,
  title,
  query,
  exclude = [],
  limit = 4,
  href,
  facets,
}: {
  nodeId?: string;
  category?: ListingCategory | null;
  title?: string;
  query?: string;
  exclude?: string[];
  limit?: 4 | 5;
  href?: string;
  facets?: Record<string, unknown>;
}) {
  const ur = useLocale() === 'ur';
  const context = useBrowseContext();
  const element = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);
  const router = useRouter();
  const { data: session } = useSession();
  useEffect(() => {
    const target = element.current;
    if (!target) return;
    if (!('IntersectionObserver' in window)) {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '180px' },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);
  const result = usePublicListings({
    ...context.query,
    categoryNodeId: nodeId ?? null,
    category: category ?? null,
    q: query ?? null,
    facets: facets ?? {},
    limit: Math.min(50, limit + exclude.length),
    enabled: visible,
  });
  const { data: favoriteIds } = useFavoriteIds();
  const add = useAddFavorite();
  const remove = useRemoveFavorite();
  const items = result.data?.items.filter((l) => !exclude.includes(l.id)).slice(0, limit) ?? [];
  const destination =
    href ??
    (nodeId ? categoryBrowseHref(nodeId) : category ? `/browse?category=${category}` : '/browse');
  function favorite(id: string) {
    if (!session) {
      router.push(
        `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`,
      );
      return;
    }
    if (favoriteIds?.has(id)) remove.mutate(id);
    else add.mutate(id);
  }
  return (
    <section
      ref={element}
      className="tl-category-listing-row py-4"
      aria-label={title ?? categoryLabel(nodeId, ur)}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-xl font-semibold tracking-tight">
          {title ?? categoryLabel(nodeId, ur)}
        </h2>
        <Link
          href={context.href(destination)}
          className="shrink-0 rounded-lg px-2 py-2 text-sm font-semibold text-brand hover:underline"
        >
          {ur ? 'مزید دیکھیں' : 'View more'} <span aria-hidden="true">{ur ? '←' : '→'}</span>
        </Link>
      </div>
      {!visible || result.isPending ? (
        <div
          className={`grid grid-cols-2 gap-4 ${limit === 5 ? 'lg:grid-cols-5' : 'lg:grid-cols-4'}`}
          aria-label="Loading listings"
          aria-busy="true"
        >
          {Array.from({ length: limit }, (_, i) => (
            <div key={i} className="h-64 rounded-xl border border-border bg-muted/30" />
          ))}
        </div>
      ) : result.isError ? (
        <div role="status" className="rounded-xl border border-dashed border-border p-6 text-sm">
          <p>{ur ? 'اشتہارات لوڈ نہیں ہوئے۔' : 'Could not load these listings.'}</p>
          <button className="mt-2 text-brand underline" onClick={() => void result.refetch()}>
            {ur ? 'دوبارہ کوشش' : 'Try again'}
          </button>
        </div>
      ) : !items.length ? (
        <div className="rounded-xl border border-dashed border-border bg-muted/10 px-4 py-3 text-sm text-muted-foreground">
          {ur
            ? 'اس قسم میں ابھی کوئی فعال اشتہار نہیں۔'
            : 'No active listings in this section yet.'}{' '}
          <Link href="/dashboard/listings/new" className="text-brand underline">
            {ur ? 'اشتہار دیں' : 'Post an ad'}
          </Link>
        </div>
      ) : (
        <div
          className={`grid grid-cols-2 gap-4 ${limit === 5 ? 'lg:grid-cols-5' : 'lg:grid-cols-4'}`}
        >
          {items.map((l) => (
            <div key={l.id} className="tl-interactive min-w-0 rounded-xl">
              <ListingCard
                listing={l}
                favorited={favoriteIds?.has(l.id) ?? false}
                onToggleFavorite={() => favorite(l.id)}
                togglingFavorite={
                  (add.isPending && add.variables === l.id) ||
                  (remove.isPending && remove.variables === l.id)
                }
              />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
export function CategoryListingRows() {
  const ur = useLocale() === 'ur';
  const [columns, setColumns] = useState<4 | 5>(4);
  const dedicated = [
    'mobiles/mobile-phones',
    'vehicles/cars',
    'bikes/motorcycles',
    'property-sale/houses',
    'electronics-appliances/video-audios',
    'mobiles/tablets',
    'property-sale/land-plots',
    'electronics-appliances/laptops',
  ];
  // Specific inventory rows first; keep every other top-level category discoverable.
  const represented = new Set(dedicated.map((id) => id.split('/')[0]));
  const rows = [
    ...dedicated,
    ...MARKETPLACE_ROOTS.filter((n) => !represented.has(n.id)).map((n) => n.id),
  ];
  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-8" data-discovery="category-rows-v1">
      <div
        className="hidden items-center justify-end gap-2 py-3 lg:flex"
        aria-label={ur ? 'قطار میں اشتہارات' : 'Cards per row'}
      >
        <span className="me-2 text-xs text-muted-foreground">
          {ur ? 'قطار میں اشتہارات' : 'Cards per row'}
        </span>
        {([4, 5] as const).map((n) => (
          <button
            key={n}
            type="button"
            aria-pressed={columns === n}
            onClick={() => setColumns(n)}
            className={`h-9 w-9 rounded-lg border text-sm ${columns === n ? 'border-brand bg-brand/10 text-brand' : 'border-border'}`}
          >
            {n}
          </button>
        ))}
      </div>
      {rows.map((id) => (
        <ListingRow key={id} nodeId={id} limit={columns} />
      ))}
    </div>
  );
}
