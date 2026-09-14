/**
 * The "view this listing" page a Browse card opens into.
 *
 * Server-rendered with ISR for the same reasons as /seller/[handle]: it
 * must be linkable with a proper preview card, crawlable, and a buyer
 * should not wait on a client round trip just to read a description.
 * Only the save/message buttons cross into a client component.
 */
import { ListingDetailActions } from '@/features/marketplace';
import { serverFetch } from '@/lib/api/server';
import {
  LISTING_CATEGORY_LABELS,
  type ListingCategory,
  type RiskLevel,
} from '@trustlens/constants';
import { RiskBadge } from '@trustlens/ui';
import { formatDateTime } from '@trustlens/utils';
import { BadgeCheck, ShieldCheck } from 'lucide-react';
import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { notFound } from 'next/navigation';

export const revalidate = 300;

const STATUS_LABEL: Record<string, string> = {
  RESERVED: 'Reserved - a deal is in progress',
  SOLD: 'Sold',
};

interface PublicListingDetail {
  id: string;
  title: string;
  description: string;
  price: number | null;
  currency: string | null;
  category: ListingCategory | null;
  condition: string | null;
  city: string | null;
  area: string | null;
  createdAt: string;
  sellerHandle: string;
  sellerDisplayName: string;
  status: string;
  negotiable: boolean;
  attributes: Record<string, string>;
  videoUrl: string | null;
  riskLevel: RiskLevel | null;
  identityVerified: boolean;
  phoneVerified: boolean;
  images: { imageUrl: string; thumbnailUrl: string | null; isPrimary: boolean }[];
  latitude: number | null;
  longitude: number | null;
}

async function getListing(id: string): Promise<PublicListingDetail | null> {
  return serverFetch<PublicListingDetail>(`/api/v1/public/listings/${encodeURIComponent(id)}`);
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const listing = await getListing(id);
  if (!listing) return { title: 'Listing not found' };

  return {
    title: `${listing.title} · TrustLens`,
    description: listing.description.slice(0, 160),
    openGraph: {
      title: listing.title,
      description: listing.description.slice(0, 160),
      images: listing.images[0] ? [listing.images[0].imageUrl] : undefined,
      type: 'website',
    },
  };
}

export default async function ListingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const listing = await getListing(id);
  if (!listing) notFound();

  const images = listing.images.length > 0 ? listing.images : [];

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-12">
      <Link href="/browse" className="text-sm text-muted-foreground hover:underline">
        ← Back to Browse
      </Link>

      {listing.status !== 'ACTIVE' && (
        <div className="mt-4 rounded-lg border border-border bg-muted/50 px-4 py-2 text-sm font-medium">
          {STATUS_LABEL[listing.status] ?? listing.status}
        </div>
      )}

      <div className="mt-4 grid gap-8 sm:grid-cols-2">
        <div>
          {images.length > 0 ? (
            <div className="space-y-2">
              <div className="relative aspect-square overflow-hidden rounded-lg border border-border bg-muted">
                <Image
                  src={images[0]!.imageUrl}
                  alt={listing.title}
                  fill
                  className="object-cover"
                  unoptimized
                  priority
                />
              </div>
              {images.length > 1 && (
                <div className="grid grid-cols-4 gap-2">
                  {images.slice(1).map((image, i) => (
                    <div
                      key={i}
                      className="relative aspect-square overflow-hidden rounded-md border border-border bg-muted"
                    >
                      <Image
                        src={image.thumbnailUrl ?? image.imageUrl}
                        alt={`${listing.title} photo ${i + 2}`}
                        fill
                        className="object-cover"
                        unoptimized
                      />
                    </div>
                  ))}
                </div>
              )}
              {listing.videoUrl && (
                // eslint-disable-next-line jsx-a11y/media-has-caption -- a seller's own upload, no captions to source
                <video
                  src={listing.videoUrl}
                  controls
                  className="aspect-video w-full rounded-lg border border-border bg-black"
                />
              )}
            </div>
          ) : (
            <div className="flex aspect-square items-center justify-center rounded-lg border border-dashed border-border bg-muted/50 text-sm text-muted-foreground">
              No photos
            </div>
          )}
        </div>

        <div>
          <h1 className="text-2xl font-bold">{listing.title}</h1>
          <p className="mt-1 text-2xl font-semibold">
            {listing.price !== null
              ? `${listing.currency ?? ''} ${listing.price.toLocaleString()}`
              : 'Price on request'}
            {listing.negotiable && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">negotiable</span>
            )}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {listing.category ? LISTING_CATEGORY_LABELS[listing.category] : 'Uncategorised'}
            {listing.condition ? ` · ${listing.condition.replace(/_/g, ' ').toLowerCase()}` : ''}
            {listing.area
              ? ` · ${listing.area}, ${listing.city}`
              : listing.city
                ? ` · ${listing.city}`
                : ''}
          </p>

          {Object.keys(listing.attributes).length > 0 && (
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              {Object.entries(listing.attributes).map(([key, value]) => (
                <div key={key} className="contents">
                  <dt className="text-muted-foreground">{key}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          )}

          {listing.latitude !== null && listing.longitude !== null && (
            // Zoom 14, not a street-level 16+: the API already rounds this
            // coordinate to ~1.1km (LOC-01), and a wide "this neighborhood"
            // view keeps the framing honest about what the pin represents.
            <a
              href={`https://www.openstreetmap.org/?mlat=${listing.latitude}&mlon=${listing.longitude}#map=14/${listing.latitude}/${listing.longitude}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-block text-sm text-primary underline-offset-4 hover:underline"
            >
              View on map
            </a>
          )}

          <div className="mt-4 rounded-lg border border-border p-4">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="flex items-center gap-1.5 truncate text-sm font-medium">
                  <span className="truncate">{listing.sellerDisplayName}</span>
                  {listing.identityVerified && (
                    <ShieldCheck
                      className="h-4 w-4 shrink-0 text-risk-low"
                      aria-label="Identity verified"
                    />
                  )}
                  {listing.phoneVerified && (
                    <BadgeCheck
                      className="h-4 w-4 shrink-0 text-muted-foreground"
                      aria-label="Phone verified"
                    />
                  )}
                </p>
                <Link
                  href={`/seller/${encodeURIComponent(listing.sellerHandle)}`}
                  className="text-sm text-primary underline-offset-4 hover:underline"
                >
                  View seller&apos;s Trust Score
                </Link>
              </div>
              {listing.riskLevel && <RiskBadge riskLevel={listing.riskLevel} />}
            </div>
          </div>

          <div className="mt-4">
            <ListingDetailActions listingId={listing.id} />
          </div>

          <p className="mt-4 text-xs text-muted-foreground">
            Listed {formatDateTime(listing.createdAt)}
          </p>
        </div>
      </div>

      <div className="mt-8 border-t border-border pt-6">
        <h2 className="text-lg font-semibold">Description</h2>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
          {listing.description}
        </p>
      </div>
    </main>
  );
}
