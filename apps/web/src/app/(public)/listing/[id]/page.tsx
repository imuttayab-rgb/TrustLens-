import { RelatedRecommendations } from '@/features/marketplace';
import { categoryLabel as nodeLabel, categoryPath, categoryBrowseHref } from '@trustlens/constants';
/**
 * The "view this listing" page a Browse card opens into.
 *
 * Server-rendered with ISR for the same reasons as /seller/[handle]: it
 * must be linkable with a proper preview card, crawlable, and a buyer
 * should not wait on a client round trip just to read a description.
 * Only the gallery, actions, and similar-listings rail cross into client
 * components.
 */
import {
  attributeIcon,
  ListingDescription,
  ListingGallery,
  ListingLocationCard,
  ListingSellerCard,
  RecordRecentlyViewed,
} from '@/features/marketplace';
import { serverFetch } from '@/lib/api/server';
import {
  LISTING_CATEGORY_LABELS,
  type ListingCategory,
  type RiskLevel,
} from '@trustlens/constants';
import { formatRelative } from '@trustlens/utils';
import { ChevronRight, ExternalLink, ShieldCheck } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

export const revalidate = 0;

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
  categoryNodeId?: string | null;
  categoryData?: Record<string, string | number>;
  publicPhone?: string | null;
  condition: string | null;
  city: string | null;
  area: string | null;
  createdAt: string;
  sellerHandle: string;
  sellerDisplayName: string;
  sellerPhotoUrl?: string | null;
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

interface SellerScore {
  score: number;
  riskLevel: RiskLevel;
  verifications: Record<string, string>;
  memberSince: string;
}

interface SellerListing {
  id: string;
  status: string;
}

interface SellerReviews {
  summary: { averageRating: number | null; reviewCount: number };
}

async function getListing(id: string): Promise<PublicListingDetail | null> {
  return serverFetch<PublicListingDetail>(`/api/v1/public/listings/${encodeURIComponent(id)}`, {
    next: { revalidate: 0 },
  });
}

async function getSellerScore(handle: string): Promise<SellerScore | null> {
  return serverFetch<SellerScore>(
    `/api/v1/public/sellers/${encodeURIComponent(handle)}/trust-score`,
  );
}

async function getSellerActiveListingsCount(handle: string): Promise<number> {
  const listings = await serverFetch<SellerListing[]>(
    `/api/v1/public/listings?seller=${encodeURIComponent(handle)}&limit=12`,
  );
  return (listings ?? []).filter((l) => l.status === 'ACTIVE').length;
}

async function getSellerReviews(handle: string): Promise<SellerReviews> {
  return (
    (await serverFetch<SellerReviews>(
      `/api/v1/public/sellers/${encodeURIComponent(handle)}/reviews`,
    )) ?? { summary: { averageRating: null, reviewCount: 0 } }
  );
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

  const [sellerScore, activeListingsCount, reviews] = await Promise.all([
    getSellerScore(listing.sellerHandle).catch(() => null),
    getSellerActiveListingsCount(listing.sellerHandle).catch(() => null),
    getSellerReviews(listing.sellerHandle).catch(() => null),
  ]);

  const images = listing.images.length > 0 ? listing.images : [];
  const categoryLabel =
    nodeLabel(listing.categoryNodeId) ||
    (listing.category ? LISTING_CATEGORY_LABELS[listing.category] : null);

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
      {listing.categoryNodeId && (
        <nav
          className="mb-3 flex flex-wrap gap-2 text-xs text-muted-foreground"
          aria-label="Category breadcrumb"
        >
          {categoryPath(listing.categoryNodeId).map((n) => (
            <Link key={n.id} href={categoryBrowseHref(n.id)} className="hover:text-brand">
              {n.label} /
            </Link>
          ))}
        </nav>
      )}
      <RecordRecentlyViewed
        listing={{
          id: listing.id,
          title: listing.title,
          price: listing.price,
          currency: listing.currency,
          category: listing.category,
          condition: listing.condition,
          city: listing.city,
          area: listing.area,
          createdAt: listing.createdAt,
          sellerHandle: listing.sellerHandle,
          sellerDisplayName: listing.sellerDisplayName,
          status: listing.status,
          negotiable: listing.negotiable,
          riskLevel: listing.riskLevel,
          // The detail page's own response doesn't carry a numeric score
          // (only the risk band) - recently-viewed is a lightweight
          // localStorage record, not a card render, so this is fine null.
          score: null,
          identityVerified: listing.identityVerified,
          phoneVerified: listing.phoneVerified,
          imageUrl: images[0]?.imageUrl ?? null,
          thumbnailUrl: images[0]?.thumbnailUrl ?? null,
          latitude: listing.latitude,
          longitude: listing.longitude,
        }}
      />

      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-1.5 text-sm text-muted-foreground"
      >
        <Link href="/" className="hover:text-foreground hover:underline">
          Home
        </Link>
        {categoryLabel && listing.category && (
          <>
            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            <Link
              href={`/browse?category=${listing.category}`}
              className="hover:text-foreground hover:underline"
            >
              {categoryLabel}
            </Link>
          </>
        )}
        <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="truncate text-foreground">{listing.title}</span>
      </nav>

      {listing.status !== 'ACTIVE' && (
        <div className="mt-4 rounded-lg border border-border bg-muted/50 px-4 py-2 text-sm font-medium">
          {STATUS_LABEL[listing.status] ?? listing.status}
        </div>
      )}

      <div className="mt-4 grid gap-8 lg:grid-cols-[1fr_360px]">
        <div className="min-w-0">
          {/* Post-an-Ad v2: the seller's product video is the gallery's first slide. */}
          <ListingGallery images={images} title={listing.title} videoUrl={listing.videoUrl} />

          <h1 className="mt-5 text-2xl font-bold sm:text-3xl">{listing.title}</h1>
          <p className="mt-1 text-2xl font-semibold text-brand">
            {listing.price !== null
              ? `${listing.currency ?? ''} ${listing.price.toLocaleString()}`
              : 'Price on request'}
            {listing.negotiable && (
              <span className="ml-2 rounded-full border border-border px-2 py-0.5 text-sm font-normal text-muted-foreground">
                Negotiable
              </span>
            )}
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            {listing.condition && <span>{listing.condition.replace(/_/g, ' ').toLowerCase()}</span>}
            {categoryLabel && <span>· {categoryLabel}</span>}
            <span>· Listing ID: #{listing.id.slice(0, 8).toUpperCase()}</span>
            <span>· Posted {formatRelative(listing.createdAt)}</span>
          </div>

          {Object.keys(listing.attributes).length > 0 && (
            <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {Object.entries(listing.attributes).map(([key, value]) => {
                const Icon = attributeIcon(key);
                return (
                  <div
                    key={key}
                    className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2"
                  >
                    <Icon className="h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
                    <div className="min-w-0">
                      <dt className="truncate text-xs text-muted-foreground">{key}</dt>
                      <dd className="truncate text-sm font-medium">{value}</dd>
                    </div>
                  </div>
                );
              })}
            </dl>
          )}

          <div className="mt-6 border-t border-border pt-6">
            <h2 className="text-lg font-semibold">Description</h2>
            <div className="mt-2">
              <ListingDescription description={listing.description} />
            </div>
          </div>

          <div className="mt-6 flex items-start gap-2 rounded-lg border border-border/60 bg-muted/30 p-3 text-sm text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
            <p>
              Never pay in advance. Inspect the item first, and meet in public.{' '}
              <Link
                href="/safety"
                className="inline-flex items-center gap-0.5 font-medium text-brand hover:underline"
              >
                Safety tips
                <ExternalLink className="h-3 w-3" aria-hidden="true" />
              </Link>
            </p>
          </div>

          <RelatedRecommendations
            listingId={listing.id}
            category={listing.category}
            nodeId={listing.categoryNodeId ?? null}
            model={
              typeof listing.categoryData?.model === 'string' ? listing.categoryData.model : null
            }
            exclude={[listing.id]}
          />
        </div>

        <div className="space-y-5 lg:sticky lg:top-20 lg:self-start">
          {listing.publicPhone && (
            <a
              href={`tel:${listing.publicPhone}`}
              className="mb-4 block rounded-xl border border-brand/30 bg-brand/5 p-4 text-center font-semibold text-brand"
            >
              Call seller · {listing.publicPhone}
            </a>
          )}
          <ListingSellerCard
            sellerHandle={listing.sellerHandle}
            sellerDisplayName={listing.sellerDisplayName}
            sellerPhotoUrl={listing.sellerPhotoUrl ?? null}
            listingId={listing.id}
            listingTitle={listing.title}
            score={sellerScore}
            activeListingsCount={activeListingsCount}
            reviews={reviews?.summary ?? null}
          />

          {listing.latitude !== null && listing.longitude !== null && (
            <ListingLocationCard
              latitude={listing.latitude}
              longitude={listing.longitude}
              city={listing.city}
              area={listing.area}
            />
          )}
        </div>
      </div>
    </main>
  );
}
