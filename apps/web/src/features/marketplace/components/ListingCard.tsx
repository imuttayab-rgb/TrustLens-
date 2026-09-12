'use client';

import { LISTING_CATEGORY_LABELS } from '@trustlens/constants';
import { cn } from '@trustlens/utils';
import { Heart, ImageOff, MessageCircle } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
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
  const router = useRouter();

  return (
    <Link
      href={`/listing/${listing.id}`}
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
              // The card itself is a Link to the listing page - the heart
              // must not also trigger that navigation.
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

        <button
          type="button"
          aria-label="Message the seller"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            router.push(`/dashboard/messages/new?listingId=${listing.id}`);
          }}
          className={cn(
            'absolute right-2 grid h-8 w-8 place-items-center rounded-full bg-background/80 text-foreground shadow backdrop-blur transition-transform hover:scale-110',
            onToggleFavorite ? 'top-12' : 'top-2',
          )}
        >
          <MessageCircle className="h-4 w-4" aria-hidden="true" />
        </button>
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
          <button
            type="button"
            onClick={(event) => {
              // The card itself is an <a> (Link to the listing page) -
              // nesting a second <a> here is invalid HTML and the browser
              // would silently close the outer one, so this opens the map
              // the same way a link would without actually being one.
              event.preventDefault();
              event.stopPropagation();
              window.open(
                `https://www.google.com/maps?q=${listing.latitude},${listing.longitude}`,
                '_blank',
                'noopener,noreferrer',
              );
            }}
            className="inline-flex items-center gap-1 text-xs text-primary underline-offset-4 hover:underline"
          >
            View on map
          </button>
        )}
      </div>
    </Link>
  );
}
