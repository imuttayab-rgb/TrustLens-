/** Feature state, queries or side-effect coordination for use saved searches. */
'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import type { ListingCategory } from '@trustlens/constants';

export interface SavedSearch {
  id: string;
  name: string;
  category: ListingCategory | null;
  categoryNodeId?: string | null;
  facets?: Record<string, unknown>;
  q: string | null;
  city: string | null;
  area: string | null;
  minPrice: number | null;
  maxPrice: number | null;
  createdAt: string | null;
}

const qk = { list: ['saved-searches'] as const };

export function useSavedSearches() {
  return useQuery<SavedSearch[]>({
    queryKey: qk.list,
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/saved-searches');
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: SavedSearch[] }).data;
    },
  });
}

export function useCreateSavedSearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      name: string;
      category: string | null;
      categoryNodeId?: string | null;
      facets?: Record<string, unknown>;
      q: string | null;
      city: string | null;
      area: string | null;
      minPrice: number | null;
      maxPrice: number | null;
    }) => {
      const result = await api.POST('/api/v1/me/saved-searches', {
        body: {
          name: input.name,
          category: input.category,
          categoryNodeId: input.categoryNodeId ?? null,
          facets: input.facets ?? {},
          q: input.q,
          city: input.city,
          area: input.area,
          minPrice: input.minPrice,
          maxPrice: input.maxPrice,
        },
      });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: qk.list });
    },
  });
}

export function useDeleteSavedSearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (searchId: string) => {
      const result = await api.DELETE('/api/v1/me/saved-searches/{search_id}', {
        params: { path: { search_id: searchId } },
      });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: qk.list });
    },
  });
}

/** Turns a saved search back into a `/browse` URL, same param names the
 * browse page itself reads. */
export function savedSearchToUrl(search: SavedSearch): string {
  const params = new URLSearchParams();
  if (search.category) params.set('category', search.category);
  if (search.categoryNodeId) params.set('categoryNodeId', search.categoryNodeId);
  if (search.facets && Object.keys(search.facets).length)
    params.set('facets', JSON.stringify(search.facets));
  if (search.q) params.set('q', search.q);
  if (search.city) params.set('city', search.city);
  if (search.area) params.set('area', search.area);
  if (search.minPrice !== null) params.set('minPrice', String(search.minPrice));
  if (search.maxPrice !== null) params.set('maxPrice', String(search.maxPrice));
  const qs = params.toString();
  return qs ? `/browse?${qs}` : '/browse';
}
