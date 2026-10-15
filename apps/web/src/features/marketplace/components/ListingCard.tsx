/** Reusable UI rendering and interaction component: ListingCard. */
'use client';

import { ProfileAvatar } from '@/features/profile';
import {
  RISK_PRESENTATION,
  listingSpecSummary,
  categoryNode,
  type RiskLevel,
} from '@trustlens/constants';
import { cn, formatRelative } from '@trustlens/utils';
import { BadgeCheck, Heart, ImageOff, MessageCircle, Share2, ShieldCheck } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useLocale } from 'next-intl';
import { useState } from 'react';
import { useBrowseContext } from '../browse-context';
import type { PublicListing } from '../hooks/use-public-listings';

const STATUS_LABEL: Record<string, string> = {
  RESERVED: 'Reserved',
  SOLD: 'Sold',
};

const TRUST_BADGE_COLOR: Record<RiskLevel, string> = {
  LOW: 'border-risk-low text-risk-low',
  MEDIUM: 'border-risk-medium text-risk-medium',
  HIGH: 'border-risk-high text-risk-high',
  UNKNOWN: 'border-risk-unknown text-risk-unknown',
};

/**
 * A denser, outlined "Trust 92" badge for the catalog card's tight bottom
 * row - the shared `RiskBadge` (a filled pill with the full "Low risk"
 * label) stays as it is everywhere else it's used; this is local to how a
 * card in a grid needs to read at a glance. Falls back to the risk label
 * when a seller has no score yet (a brand-new UNKNOWN account).
 */
function TrustBadge({ riskLevel, score }: { riskLevel: RiskLevel; score: number | null }) {
  return (
    <span
      className={cn(
        'shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-bold',
        TRUST_BADGE_COLOR[riskLevel],
      )}
    >
      {score !== null ? `Trust ${score}` : RISK_PRESENTATION[riskLevel].label}
    </span>
  );
}

export function ListingCard({
  listing,
  favorited,
  onToggleFavorite,
  togglingFavorite,
  layout = 'grid',
}: {
  listing: PublicListing;
  /** Omit entirely (rather than passing false) to hide the heart button. */
  favorited?: boolean;
  onToggleFavorite?: () => void;
  togglingFavorite?: boolean;
  layout?: 'grid' | 'list';
}) {
  const router = useRouter();
  const ur = useLocale() === 'ur';
  const context = useBrowseContext();
  const [shareMessage, setShareMessage] = useState('');
  const facts = listingSpecSummary(listing.categoryNodeId, listing.categoryData, ur);
  const physical =
    !categoryNode(listing.categoryNodeId) ||
    categoryNode(listing.categoryNodeId)?.conditionRequired;
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
      setShareMessage(ur ? 'لنک کاپی ہو گیا' : 'Link copied');
    } catch {
      setShareMessage(
        ur
          ? 'لنک کاپی نہیں ہوا؛ اشتہار کھول کر ایڈریس کاپی کریں۔'
          : 'Could not copy. Open the listing and copy its address.',
      );
    }
  }

  return (
    <article
      className={cn(
        'tl-listing-card group relative h-full overflow-hidden rounded-xl border border-border bg-card transition-colors hover:border-brand/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        layout === 'list' ? 'flex' : 'block',
      )}
    >
      <Link
        href={context.href(`/listing/${listing.id}`)}
        className="absolute inset-0 z-10 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="sr-only">{listing.title}</span>
      </Link>
      <div
        className={cn(
          'relative bg-muted/50',
          layout === 'list'
            ? 'min-h-44 w-28 shrink-0 self-stretch sm:w-52'
            : 'aspect-square w-full',
        )}
      >
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
          <span className="absolute start-2 top-2 rounded-full bg-foreground/90 px-2 py-0.5 text-xs font-semibold text-background">
            {statusLabel}
          </span>
        )}

        <button
          type="button"
          aria-label={ur ? 'اشتہار شیئر کریں' : 'Share this listing'}
          onClick={(event) => void share(event)}
          className="absolute bottom-2 start-2 z-20 grid h-10 w-10 place-items-center rounded-full bg-background/80 text-foreground shadow backdrop-blur transition-opacity hover:scale-110 focus-visible:opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100"
        >
          <Share2 className="h-4 w-4" aria-hidden="true" />
        </button>

        {onToggleFavorite && (
          <button
            type="button"
            aria-label={
              favorited
                ? ur
                  ? 'پسندیدہ سے ہٹائیں'
                  : 'Remove from favorites'
                : ur
                  ? 'پسندیدہ میں محفوظ کریں'
                  : 'Save to favorites'
            }
            aria-pressed={favorited}
            disabled={togglingFavorite}
            onClick={(event) => {
              // The card itself is a Link to the listing page - the heart
              // must not also trigger that navigation.
              event.preventDefault();
              event.stopPropagation();
              onToggleFavorite();
            }}
            className="absolute end-2 top-2 z-20 grid h-10 w-10 place-items-center rounded-full bg-background/80 text-foreground shadow backdrop-blur transition-transform hover:scale-110 disabled:pointer-events-none disabled:opacity-60"
          >
            <Heart
              className={cn('h-4 w-4', favorited && 'fill-current text-destructive')}
              aria-hidden="true"
            />
          </button>
        )}

        <button
          type="button"
          aria-label={ur ? 'فروخت کنندہ کو پیغام بھیجیں' : 'Message the seller'}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            router.push(`/messages/new?listingId=${listing.id}`);
          }}
          className={cn(
            'absolute end-2 z-20 grid h-10 w-10 place-items-center rounded-full bg-background/80 text-foreground shadow backdrop-blur transition-transform hover:scale-110',
            onToggleFavorite ? 'top-14' : 'top-2',
          )}
        >
          <MessageCircle className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <div className={cn('min-w-0 flex-1 space-y-2 p-3', layout === 'list' && 'sm:p-5')}>
        <p
          className={cn(
            'line-clamp-2 break-words text-sm font-medium',
            layout === 'list' && 'sm:text-base',
          )}
        >
          {listing.title}
        </p>
        <p className="text-base font-semibold tabular-nums">
          {listing.price !== null
            ? `${listing.currency ?? ''} ${listing.price.toLocaleString()}`
            : ur
              ? 'قیمت پوچھیں'
              : 'Price on request'}
          {listing.negotiable && (
            <span className="ms-1.5 text-xs font-normal text-muted-foreground">
              {ur ? 'قابلِ مذاکرہ' : 'negotiable'}
            </span>
          )}
        </p>
        {facts.length > 0 && (
          <p className="line-clamp-2 text-xs leading-5 text-muted-foreground">
            {facts.join(' · ')}
          </p>
        )}
        <p className="truncate text-xs text-muted-foreground">
          {physical && listing.condition
            ? `${ur ? (({ NEW: 'نیا', LIKE_NEW: 'نئے جیسا', USED: 'استعمال شدہ', FOR_PARTS: 'پرزوں کے لیے' } as Record<string, string>)[listing.condition] ?? listing.condition) : listing.condition.replace(/_/g, ' ').toLowerCase()} · `
            : ''}
          {listing.area
            ? `${listing.area}, ${listing.city}`
            : listing.city
              ? `${listing.city}`
              : ''}
          {' · '}
          {formatRelative(listing.createdAt)}
        </p>
        <div className="flex items-center justify-between gap-2 pt-0.5">
          <Link
            href={`/seller/${listing.sellerHandle}`}
            className="relative z-20 flex min-w-0 items-center gap-1.5 truncate rounded text-xs text-muted-foreground hover:underline"
          >
            <ProfileAvatar
              src={listing.sellerPhotoUrl}
              name={listing.sellerDisplayName}
              size={22}
            />
            <span className="truncate">{listing.sellerDisplayName}</span>
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
          </Link>
          {listing.riskLevel && (
            <TrustBadge riskLevel={listing.riskLevel as RiskLevel} score={listing.score} />
          )}
        </div>
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
            className="relative z-20 inline-flex min-h-9 items-center gap-1 text-xs text-primary underline-offset-4 hover:underline"
          >
            {ur ? 'نقشے پر دیکھیں' : 'View on map'}
          </button>
        )}
        {shareMessage && (
          <p role="status" className="text-xs text-brand">
            {shareMessage}
          </p>
        )}
      </div>
    </article>
  );
}
