/** Reusable UI rendering and interaction component: RecentlyViewedStrip. */
'use client';

import { stagger, usePrefersReducedMotion } from '@/lib/motion';
import { cn } from '@trustlens/utils';
import { History } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { clearRecentlyViewed, useRecentlyViewed } from '../hooks/use-recently-viewed';

/** MKT-01's "recently viewed" rail - local history only, see `use-recently-viewed`. */
export function RecentlyViewedStrip({ excludeId }: { excludeId?: string }) {
  const reduced = usePrefersReducedMotion();
  const items = useRecentlyViewed(excludeId);
  if (items.length === 0) return null;

  return (
    <section
      className={cn(
        'rounded-xl border border-border bg-card p-4 shadow-sm',
        !reduced && 'animate-fade-up',
      )}
    >
      <h2 className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
        <History className="h-4 w-4" aria-hidden="true" />
        Recently viewed
        <button type="button" onClick={clearRecentlyViewed} className="ml-auto text-xs underline">
          Clear history
        </button>
      </h2>
      <div className="mt-3 flex gap-3 overflow-x-auto pb-1">
        {items.map((listing, index) => (
          <Link
            key={listing.id}
            href={`/listing/${listing.id}`}
            style={!reduced ? stagger(index, 50) : undefined}
            className={cn(
              'w-32 shrink-0 overflow-hidden rounded-lg border border-border bg-background transition-all duration-200 hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-md',
              !reduced && 'animate-fade-in',
            )}
          >
            <div className="relative aspect-square w-full bg-muted/50">
              {(listing.thumbnailUrl ?? listing.imageUrl) && (
                <Image
                  src={listing.thumbnailUrl ?? listing.imageUrl ?? ''}
                  alt={listing.title}
                  fill
                  className="object-cover"
                  unoptimized
                />
              )}
            </div>
            <p className="truncate p-1.5 text-xs">{listing.title}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
