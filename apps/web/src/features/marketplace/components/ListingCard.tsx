'use client';

import { LISTING_CATEGORY_LABELS, type RiskLevel } from '@trustlens/constants';
import { RiskBadge } from '@trustlens/ui';
import { cn, formatRelative } from '@trustlens/utils';
import { BadgeCheck, Heart, ImageOff, MessageCircle, Share2, ShieldCheck } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { PublicListing } from '../hooks/use-public-listings';

const STATUS_LABEL: Record<string, string> = {
  RESERVED: 'Reserved',
  SOLD: 'Sold',
};

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
  const statusLabel = STATUS_LABEL[listing.status];

  async function share(event: React.MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    const url = `${window.location.origin}/listing/${listing.id}`;
    if (navigator.share) {
      try {
        await navigator.share({ title: listing.title, url });
      } catch {
        // The user cancelled the native share sheet - not an error.
      }
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      // Clipboard access can be denied (permissions, non-HTTPS context);
      // there's no good fallback UI on a catalog card for that failure.
    }
  }

  return (
    <Link
      href={`/listing/${listing.id}`}
      className="group block overflow-hidden rounded-lg border border-border bg-card transition-colors hover:border-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="relative aspect-square w-full bg-muted/50">
        {(listing.thumbnailUrl ?? listing.imageUrl) ? (
          <Image
            src={listing.thumbnailUrl ?? listing.imageUrl ?? ''}
            alt={listing.title}
            fill
            className={cn(
              'object-cover transition-transform duration-300 group-hover:scale-105',
              statusLabel && 'opacity-60',
            )}
            unoptimized // Presigned S3 URLs should not be cached/optimized by Next.js image proxy
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <ImageOff className="h-8 w-8 opacity-30" aria-hidden="true" />
          </div>
        )}

        {statusLabel && (
          <span className="absolute left-2 top-2 rounded-full bg-foreground/90 px-2 py-0.5 text-xs font-semibold text-background">
            {statusLabel}
          </span>
        )}

        <button
          type="button"
          aria-label="Share this listing"
          onClick={(event) => void share(event)}
          className="absolute bottom-2 left-2 grid h-8 w-8 place-items-center rounded-full bg-background/80 text-foreground opacity-0 shadow backdrop-blur transition-opacity hover:scale-110 group-hover:opacity-100"
        >
          <Share2 className="h-4 w-4" aria-hidden="true" />
        </button>

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
          {listing.negotiable && (
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">negotiable</span>
          )}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {listing.category ? LISTING_CATEGORY_LABELS[listing.category] : 'Uncategorised'}
          {listing.condition ? ` · ${listing.condition.replace(/_/g, ' ').toLowerCase()}` : ''}
          {listing.area
            ? ` · ${listing.area}, ${listing.city}`
            : listing.city
              ? ` · ${listing.city}`
              : ''}
        </p>
        <div className="flex items-center justify-between gap-2">
          <p className="flex min-w-0 items-center gap-1 truncate text-xs text-muted-foreground">
            <span className="truncate">by {listing.sellerDisplayName}</span>
            {listing.identityVerified && (
              <ShieldCheck
                className="h-3.5 w-3.5 shrink-0 text-risk-low"
                aria-label="Identity verified"
              />
            )}
            {listing.phoneVerified && (
              <BadgeCheck
                className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                aria-label="Phone verified"
              />
            )}
          </p>
          {listing.riskLevel && (
            <RiskBadge
              riskLevel={listing.riskLevel as RiskLevel}
              className="shrink-0 px-1.5 py-0 text-[10px]"
            />
          )}
        </div>
        <p className="truncate text-xs text-muted-foreground">
          Listed {formatRelative(listing.createdAt)}
        </p>
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
              // Zoom 14, not a street-level 16+: coordinates returned by the
              // API are already rounded to ~1.1km (LOC-01), and opening on a
              // wide, "this neighborhood" view keeps the framing honest about
              // what the pin actually represents.
              window.open(
                `https://www.openstreetmap.org/?mlat=${listing.latitude}&mlon=${listing.longitude}#map=14/${listing.latitude}/${listing.longitude}`,
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
