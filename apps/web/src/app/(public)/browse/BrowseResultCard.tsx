/** Next.js route/layout composition for (public)/browse: BrowseResultCard. */
'use client';

import type { PublicListing } from '@/features/marketplace';
import { cn, formatRelative } from '@trustlens/utils';
import { Clock3, Heart, ImageOff, Mail, ContactRound, Phone } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import styles from './browse-reference.module.css';

const CONDITIONS: Record<string, string> = {
  NEW: 'New',
  LIKE_NEW: 'Like New',
  USED: 'Used',
  FOR_PARTS: 'For parts',
};

export function BrowseResultCard({
  listing,
  layout,
  favorited,
  onToggleFavorite,
  togglingFavorite,
}: {
  listing: PublicListing;
  layout: 'grid' | 'list';
  favorited: boolean;
  onToggleFavorite: () => void;
  togglingFavorite: boolean;
}) {
  const href = `/listing/${listing.id}`;
  const photo = listing.thumbnailUrl ?? listing.imageUrl;
  const seller = listing.sellerHandle ? `@${listing.sellerHandle}` : listing.sellerDisplayName;
  const location = [listing.area, listing.city].filter(Boolean).join(', ');
  const status =
    listing.status === 'SOLD' ? 'Sold' : listing.status === 'RESERVED' ? 'Reserved' : null;
  return (
    <article className={cn(styles.card, layout === 'list' && styles.listCard)}>
      <div className={styles.photo}>
        <Link href={href} aria-label={`View ${listing.title}`} className={styles.photoLink}>
          {photo ? (
            <Image
              src={photo}
              alt={listing.title}
              fill
              unoptimized
              className="object-cover"
              sizes="(min-width: 1200px) 25vw, (min-width: 640px) 42vw, 90vw"
            />
          ) : (
            <span className={styles.noPhoto}>
              <ImageOff aria-hidden="true" />
              <span className="sr-only">No photo available</span>
            </span>
          )}
        </Link>
        {status && <span className={styles.status}>{status}</span>}
        <button
          type="button"
          className={cn(styles.heart, favorited && styles.favorited)}
          aria-label={
            favorited
              ? `Remove ${listing.title} from favourites`
              : `Save ${listing.title} to favourites`
          }
          aria-pressed={favorited}
          disabled={togglingFavorite}
          onClick={onToggleFavorite}
        >
          <Heart aria-hidden="true" fill={favorited ? 'currentColor' : 'none'} />
        </button>
      </div>
      <div className={styles.cardBody}>
        <Link href={href} className={styles.cardTitleLink}>
          <p className={styles.price}>
            {listing.price === null
              ? 'Price on request'
              : `${listing.currency ?? 'PKR'} ${listing.price.toLocaleString('en-PK')}`}
          </p>
          <h3 className={styles.cardTitle} title={listing.title}>
            {listing.title}
          </h3>
        </Link>
        <div className={styles.metadata}>
          <p
            title={[listing.condition ? CONDITIONS[listing.condition] : null, location]
              .filter(Boolean)
              .join(' · ')}
          >
            {listing.condition
              ? (CONDITIONS[listing.condition] ?? listing.condition)
              : 'Not specified'}
            {location && (
              <>
                <span aria-hidden="true"> · </span>
                {location}
              </>
            )}
          </p>
          <time dateTime={listing.createdAt} title={listing.createdAt}>
            <Clock3 aria-hidden="true" />
            {formatRelative(listing.createdAt)}
          </time>
        </div>
        <div className={styles.sellerRow}>
          <Link
            href={`/seller/${encodeURIComponent(listing.sellerHandle)}`}
            className={styles.seller}
            title={seller}
          >
            <span className={styles.avatar} aria-hidden="true">
              {(listing.sellerDisplayName || listing.sellerHandle || 'S').charAt(0)}
            </span>
            <span>{seller}</span>
          </Link>
          <div className={styles.sellerChecks}>
            <span
              className={cn(styles.checkIcon, !listing.identityVerified && styles.unverified)}
              title={listing.identityVerified ? 'Identity verified' : 'Identity not verified'}
              role="img"
              aria-label={listing.identityVerified ? 'Identity verified' : 'Identity not verified'}
            >
              <ContactRound aria-hidden="true" />
            </span>
            <span
              className={cn(styles.checkIcon, !listing.phoneVerified && styles.unverified)}
              title={listing.phoneVerified ? 'Phone verified' : 'Phone not verified'}
              role="img"
              aria-label={listing.phoneVerified ? 'Phone verified' : 'Phone not verified'}
            >
              <Phone aria-hidden="true" />
            </span>
            <Link
              href={`/messages/new?listingId=${encodeURIComponent(listing.id)}`}
              className={styles.checkIcon}
              title="Message seller"
              aria-label={`Message ${seller}`}
            >
              <Mail aria-hidden="true" />
            </Link>
          </div>
          <span
            className={cn(
              styles.trust,
              listing.score === null
                ? styles.unscored
                : listing.score < 60
                  ? styles.lowTrust
                  : listing.score < 80
                    ? styles.mediumTrust
                    : '',
            )}
            title="Seller trust score; open the listing to review seller checks"
          >
            {listing.score === null ? 'Not scored' : `Trust ${listing.score}`}
          </span>
        </div>
      </div>
    </article>
  );
}
