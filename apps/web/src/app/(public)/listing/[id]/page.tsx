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
import { LISTING_CATEGORY_LABELS, type ListingCategory } from '@trustlens/constants';
import { formatDateTime } from '@trustlens/utils';
import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { notFound } from 'next/navigation';

export const revalidate = 300;

interface PublicListingDetail {
  id: string;
  title: string;
  description: string;
  price: number | null;
  currency: string | null;
  category: ListingCategory | null;
  city: string | null;
  area: string | null;
  createdAt: string;
  sellerHandle: string;
  sellerDisplayName: string;
  images: { imageUrl: string; isPrimary: boolean }[];
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
                        src={image.imageUrl}
                        alt={`${listing.title} photo ${i + 2}`}
                        fill
                        className="object-cover"
                        unoptimized
                      />
                    </div>
                  ))}
                </div>
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
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {listing.category ? LISTING_CATEGORY_LABELS[listing.category] : 'Uncategorised'}
            {listing.area
              ? ` · ${listing.area}, ${listing.city}`
              : listing.city
                ? ` · ${listing.city}`
                : ''}
          </p>

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
            <p className="text-sm font-medium">{listing.sellerDisplayName}</p>
            <Link
              href={`/seller/${encodeURIComponent(listing.sellerHandle)}`}
              className="text-sm text-primary underline-offset-4 hover:underline"
            >
              View seller&apos;s Trust Score
            </Link>
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
