import { LISTING_CATEGORY_LABELS } from '@trustlens/constants';
import { ImageOff } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import type { PublicListing } from '../hooks/use-public-listings';

export function ListingCard({ listing }: { listing: PublicListing }) {
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
          {listing.city ? ` · ${listing.city}` : ''}
        </p>
        <p className="truncate text-xs text-muted-foreground">by {listing.sellerDisplayName}</p>
      </div>
    </Link>
  );
}
