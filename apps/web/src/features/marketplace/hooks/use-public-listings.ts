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
  city: string | null;
  area: string | null;
  createdAt: string;
  sellerHandle: string;
  sellerDisplayName: string;
  imageUrl: string | null;
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
  /** One seller's own active listings, by handle - the public storefront. */
  sellerHandle?: string | null;
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
