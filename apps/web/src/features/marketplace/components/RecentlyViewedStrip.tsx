'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useRecentlyViewed } from '../hooks/use-recently-viewed';

/** MKT-01's "recently viewed" rail - local history only, see `use-recently-viewed`. */
export function RecentlyViewedStrip({ excludeId }: { excludeId?: string }) {
  const items = useRecentlyViewed(excludeId);
  if (items.length === 0) return null;

  return (
    <section className="mt-6">
      <h2 className="text-sm font-semibold text-muted-foreground">Recently viewed</h2>
      <div className="mt-2 flex gap-3 overflow-x-auto pb-2">
        {items.map((listing) => (
          <Link
            key={listing.id}
            href={`/listing/${listing.id}`}
            className="w-28 shrink-0 overflow-hidden rounded-lg border border-border bg-card transition-colors hover:border-foreground/30"
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
