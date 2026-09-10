'use client';

import { LISTING_CATEGORY_LABELS } from '@trustlens/constants';
import { cn } from '@trustlens/utils';
import { Heart, ImageOff } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import type { PublicListing } from '../hooks/use-public-listings';

export function ListingCard({
  listing,
  favorited,
  onToggleFavorite,
  togglingFavorite,
}: {
  listing: PublicListing;
  /** Omit entirely (rather than passing false) to hide the heart button. */
  favorited?: boolean;
  onToggleFavorite?: () => void;
  togglingFavorite?: boolean;
}) {
  return (
    <Link
      href={`/seller/${encodeURIComponent(listing.sellerHandle)}`}
      className="group block overflow-hidden rounded-lg border border-border bg-card transition-colors hover:border-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="relative aspect-square w-full bg-muted/50">
        {listing.imageUrl ? (
          <Image
            src={listing.imageUrl}
            alt={listing.title}
            fill
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            unoptimized // Presigned S3 URLs should not be cached/optimized by Next.js image proxy
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <ImageOff className="h-8 w-8 opacity-30" aria-hidden="true" />
          </div>
        )}

        {onToggleFavorite && (
          <button
            type="button"
            aria-label={favorited ? 'Remove from favorites' : 'Save to favorites'}
            aria-pressed={favorited}
            disabled={togglingFavorite}
            onClick={(event) => {
              // The card itself is a Link to the seller page - the heart must
              // not also trigger that navigation.
              event.preventDefault();
              event.stopPropagation();
              onToggleFavorite();
            }}
            className="absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-full bg-background/80 text-foreground shadow backdrop-blur transition-transform hover:scale-110 disabled:pointer-events-none disabled:opacity-60"
          >
            <Heart
              className={cn('h-4 w-4', favorited && 'fill-current text-destructive')}
              aria-hidden="true"
            />
          </button>
        )}
      </div>
      <div className="space-y-1 p-3">
        <p className="truncate text-sm font-medium">{listing.title}</p>
        <p className="text-sm font-semibold">
          {listing.price !== null
            ? `${listing.currency ?? ''} ${listing.price.toLocaleString()}`
            : 'Price on request'}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {listing.category ? LISTING_CATEGORY_LABELS[listing.category] : 'Uncategorised'}
          {listing.area
            ? ` · ${listing.area}, ${listing.city}`
            : listing.city
              ? ` · ${listing.city}`
              : ''}
        </p>
        <p className="truncate text-xs text-muted-foreground">by {listing.sellerDisplayName}</p>
        {listing.latitude !== null && listing.longitude !== null && (
          <a
            href={`https://www.google.com/maps?q=${listing.latitude},${listing.longitude}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(event) => event.stopPropagation()}
            className="inline-flex items-center gap-1 text-xs text-primary underline-offset-4 hover:underline"
          >
            View on map
          </a>
        )}
      </div>
    </Link>
  );
}
