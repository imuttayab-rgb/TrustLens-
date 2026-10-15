/** Feature state, queries or side-effect coordination for use listings. */
'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import type { ListingCategory } from '@trustlens/constants';

export interface ListingAnalysis {
  riskScore: number;
  confidence: number;
  analyzerType: string;
  provider: string;
  modelName: string;
  analysedAt: string;
  summary: string | null;
  labels: { code: string; confidence: number; evidence?: string | null }[];
  priceDeviationPct: number | null;
}

export interface Listing {
  id: string;
  sellerId: string;
  title: string;
  description: string;
  status:
    'DRAFT' | 'ACTIVE' | 'ANALYSING' | 'FLAGGED' | 'REMOVED' | 'EXPIRED' | 'RESERVED' | 'SOLD';
  source: string;
  createdAt: string;
  price: number | null;
  currency: string | null;
  category: ListingCategory | null;
  categoryNodeId: string | null;
  categoryData: Record<string, string | number>;
  showPhone: boolean;
  condition: string | null;
  city: string | null;
  area: string | null;
  /** Private full address (seller-only). */
  addressLine: string | null;
  latitude: number | null;
  longitude: number | null;
  countryCode: string | null;
  negotiable: boolean;
  attributes: Record<string, string>;
  videoFileId: string | null;
  updatedAt: string | null;
  analysis: ListingAnalysis | null;
}

/**
 * Mirrors the generated request type, which uses `| null` rather than
 * `| undefined`: the API distinguishes "field omitted" from "field cleared",
 * and under exactOptionalPropertyTypes the two are not interchangeable.
 */
export interface ListingPayload {
  title: string;
  description: string;
  price?: number | null;
  currency?: string | null;
  category?: ListingCategory | null;
  categoryNodeId?: string | null;
  showPhone?: boolean;
  condition?: string | null;
  city?: string | null;
  area?: string | null;
  addressLine?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  countryCode?: string | null;
  negotiable: boolean;
  attributes?: Record<string, string>;
  videoFileId?: string | null;
}

export function useListings({ limit = 20, offset = 0 } = {}) {
  return useQuery<{ items: Listing[]; total: number }>({
    queryKey: qk.listing.list(limit, offset),
    queryFn: async () => {
      const result = await api.GET('/api/v1/listings', {
        params: { query: { limit, offset } },
      });
      if (result.error) throw toApiError(result.error);
      const body = result.data as { data: Listing[]; meta?: { pagination?: { total: number } } };
      return { items: body.data, total: body.meta?.pagination?.total ?? body.data.length };
    },
  });
}

export function useListing(id: string | null) {
  return useQuery<Listing>({
    queryKey: qk.listing.byId(id ?? 'none'),
    enabled: Boolean(id),
    queryFn: async () => {
      const result = await api.GET('/api/v1/listings/{listing_id}', {
        params: { path: { listing_id: id as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: Listing }).data;
    },
    // A listing sits in ANALYSING for the length of a worker round trip, so
    // poll while it is unsettled and stop as soon as it is not.
    refetchInterval: (query) => (query.state.data?.status === 'ANALYSING' ? 2_000 : false),
  });
}

/** Every mutation invalidates the whole listing tree; the score depends on it. */
function useInvalidate() {
  const queryClient = useQueryClient();
  return async () => {
    await queryClient.invalidateQueries({ queryKey: qk.listing.all });
    await queryClient.invalidateQueries({ queryKey: qk.seller.me });
  };
}

export function useCreateListing() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (payload: ListingPayload) => {
      const result = await api.POST('/api/v1/listings', { body: payload });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: { listing: Listing } }).data.listing;
    },
    onSuccess: invalidate,
  });
}

export function useUpdateListing(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (payload: ListingPayload) => {
      const result = await api.PUT('/api/v1/listings/{listing_id}', {
        params: { path: { listing_id: id } },
        body: payload,
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: { listing: Listing } }).data.listing;
    },
    onSuccess: invalidate,
  });
}

export function useDeleteListing() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (id: string) => {
      const result = await api.DELETE('/api/v1/listings/{listing_id}', {
        params: { path: { listing_id: id } },
      });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: invalidate,
  });
}

export function useAnalyseListing() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (id: string) => {
      const result = await api.POST('/api/v1/listings/{listing_id}/analyse', {
        params: { path: { listing_id: id } },
      });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: invalidate,
  });
}

export interface ListingImage {
  imageId: string;
  position: number;
  isPrimary: boolean;
  width: number | null;
  height: number | null;
  url: string | null;
  thumbnailUrl: string | null;
}

export interface AddListingImageResponse {
  imageId: string;
  position: number;
  isPrimary: boolean;
  width: number | null;
  height: number | null;
  isDuplicate: boolean;
  duplicateOf: string | null;
}

export function useListingImages(listingId: string | null) {
  return useQuery<ListingImage[]>({
    queryKey: [...qk.listing.byId(listingId ?? 'none'), 'images'],
    enabled: Boolean(listingId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/listings/{listing_id}/images', {
        params: { path: { listing_id: listingId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: ListingImage[] }).data;
    },
  });
}

export function useAddListingImage(listingId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (fileId: string) => {
      const result = await api.POST('/api/v1/listings/{listing_id}/images', {
        params: { path: { listing_id: listingId } },
        body: { fileId },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: AddListingImageResponse }).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [...qk.listing.byId(listingId), 'images'],
      });
    },
  });
}

export function useManageListingPhotos(listingId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (action: { removeId: string } | { order: string[] }) => {
      const r =
        'removeId' in action
          ? await api.DELETE('/api/v1/listings/{listing_id}/images/{image_id}', {
              params: { path: { listing_id: listingId, image_id: action.removeId } },
            })
          : await api.PUT('/api/v1/listings/{listing_id}/images/order', {
              params: { path: { listing_id: listingId } },
              body: { imageIds: action.order },
            });
      if (r.error) throw toApiError(r.error);
    },
    onSuccess: invalidate,
  });
}
