'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { useQuery } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import type { ListingCategory } from '@trustlens/constants';

export type SortOrder = 'newest' | 'price_asc' | 'price_desc';

export interface PublicListing {
  id: string;
  title: string;
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
  riskLevel: string | null;
  score: number | null;
  identityVerified: boolean;
  phoneVerified: boolean;
  imageUrl: string | null;
  thumbnailUrl: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface BrowseListingsParams {
  category?: ListingCategory | null;
  q?: string | null;
  city?: string | null;
  area?: string | null;
  minPrice?: number | null;
  maxPrice?: number | null;
  /** One seller's own listings, by handle - the public storefront. Unlike
   * the anonymous catalog, this also returns their reserved/sold history. */
  sellerHandle?: string | null;
  attributeKey?: string | null;
  attributeValue?: string | null;
  /** "Nearby" (MKT-01) / radius search (LOC-01) - all three or none. */
  nearLatitude?: number | null;
  nearLongitude?: number | null;
  radiusKm?: number | null;
  condition?: string | null;
  minTrustScore?: number | null;
  maxTrustScore?: number | null;
  verifiedOnly?: boolean;
  sort?: SortOrder;
  limit?: number;
  offset?: number;
}

/**
 * The buyer-facing catalog read. Unauthenticated on purpose - `api.GET`
 * simply sends no Authorization header when there is no session, and the
 * endpoint does not require one.
 */
export function usePublicListings({
  category = null,
  q = null,
  city = null,
  area = null,
  minPrice = null,
  maxPrice = null,
  sellerHandle = null,
  attributeKey = null,
  attributeValue = null,
  nearLatitude = null,
  nearLongitude = null,
  radiusKm = null,
  condition = null,
  minTrustScore = null,
  maxTrustScore = null,
  verifiedOnly = false,
  sort = 'newest',
  limit = 20,
  offset = 0,
}: BrowseListingsParams = {}) {
  return useQuery<{ items: PublicListing[]; total: number }>({
    queryKey: qk.listing.public({
      category,
      q,
      city,
      area,
      minPrice,
      maxPrice,
      sellerHandle,
      attributeKey,
      attributeValue,
      nearLatitude,
      nearLongitude,
      radiusKm,
      condition,
      minTrustScore,
      maxTrustScore,
      verifiedOnly,
      sort,
      limit,
      offset,
    }),
    queryFn: async () => {
      const result = await api.GET('/api/v1/public/listings', {
        params: {
          query: {
            category,
            q,
            city,
            area,
            min_price: minPrice,
            max_price: maxPrice,
            seller: sellerHandle,
            attributeKey,
            attributeValue,
            nearLatitude,
            nearLongitude,
            radiusKm,
            condition,
            minTrustScore,
            maxTrustScore,
            verifiedOnly,
            sort,
            limit,
            offset,
          },
        },
      });
      if (result.error) throw toApiError(result.error);
      const body = result.data as {
        data: PublicListing[];
        meta?: { pagination?: { total: number } };
      };
      return { items: body.data, total: body.meta?.pagination?.total ?? body.data.length };
    },
  });
}

/**
 * Just enough of the public listing detail to drive SafeMeet's venue
 * suggestions (which are keyed by city) - not the full page fetch that
 * `/listing/[id]/page.tsx` does server-side.
 */
export function useListingCity(listingId: string | null) {
  return useQuery<{ city: string | null }>({
    queryKey: qk.listing.publicById(listingId ?? 'none'),
    enabled: Boolean(listingId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/public/listings/{listing_id}', {
        params: { path: { listing_id: listingId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: { city: string | null } }).data;
    },
  });
}

export interface MessageThreadListing {
  id: string;
  title: string;
  price: number | null;
  currency: string | null;
  status: string;
  createdAt: string;
  sellerHandle: string;
  images: { imageUrl: string; thumbnailUrl: string | null }[];
}

/** Just enough of the public listing detail to render the "what this
 * conversation is about" card at the top of a message thread. */
export function useMessageThreadListing(listingId: string | null) {
  return useQuery<MessageThreadListing>({
    queryKey: [...qk.listing.publicById(listingId ?? 'none'), 'thread-card'],
    enabled: Boolean(listingId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/public/listings/{listing_id}', {
        params: { path: { listing_id: listingId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: MessageThreadListing }).data;
    },
  });
}
