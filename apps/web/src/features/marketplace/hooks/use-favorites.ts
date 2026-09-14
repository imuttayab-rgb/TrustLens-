'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { useSession } from '@/lib/auth/use-session';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import type { PublicListing } from './use-public-listings';

/**
 * Every listing id the signed-in user has saved, as a Set for O(1) "is this
 * card already favorited" checks while rendering a page of results.
 *
 * Anonymous on `/browse` is a normal state, not an error - `enabled` just
 * skips the call rather than 401ing, and the query resolves to an empty set.
 */
export function useFavoriteIds() {
  const { data: session } = useSession();
  return useQuery<Set<string>>({
    queryKey: qk.favorite.ids,
    enabled: Boolean(session),
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/favorites/ids');
      if (result.error) throw toApiError(result.error);
      const body = result.data as { data: { listingIds: string[] } };
      return new Set(body.data.listingIds);
    },
    staleTime: 30_000,
  });
}

export function useMyFavorites({ limit = 20, offset = 0 } = {}) {
  return useQuery<{ items: PublicListing[]; total: number }>({
    queryKey: qk.favorite.list(limit, offset),
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/favorites', {
        params: { query: { limit, offset } },
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

function useInvalidateFavorites() {
  const queryClient = useQueryClient();
  return async () => {
    await queryClient.invalidateQueries({ queryKey: qk.favorite.ids });
    await queryClient.invalidateQueries({ queryKey: ['favorites', 'list'] });
  };
}

/**
 * Shared optimistic-toggle logic for add/remove - the heart on a catalog
 * card should flip the instant it's clicked, not after a round trip. Both
 * mutations below cancel any in-flight refetch of the id set first (so it
 * can't overwrite the optimistic value), snapshot it for rollback, then
 * flip the one id being toggled.
 */
interface OptimisticContext {
  previous: Set<string> | undefined;
}

function useOptimisticToggle(nextHasId: (listingId: string) => boolean) {
  const queryClient = useQueryClient();
  return {
    onMutate: async (listingId: string): Promise<OptimisticContext> => {
      await queryClient.cancelQueries({ queryKey: qk.favorite.ids });
      const previous = queryClient.getQueryData<Set<string>>(qk.favorite.ids);
      queryClient.setQueryData<Set<string>>(qk.favorite.ids, (current) => {
        const next = new Set(current ?? []);
        if (nextHasId(listingId)) next.add(listingId);
        else next.delete(listingId);
        return next;
      });
      return { previous };
    },
    onError: (_error: unknown, _listingId: string, context: OptimisticContext | undefined) => {
      if (context?.previous) queryClient.setQueryData(qk.favorite.ids, context.previous);
    },
  };
}

export function useAddFavorite() {
  const invalidate = useInvalidateFavorites();
  const optimistic = useOptimisticToggle(() => true);
  return useMutation({
    mutationFn: async (listingId: string) => {
      const result = await api.POST('/api/v1/me/favorites', { body: { listingId } });
      if (result.error) throw toApiError(result.error);
    },
    onMutate: optimistic.onMutate,
    onError: optimistic.onError,
    onSuccess: invalidate,
  });
}

export function useRemoveFavorite() {
  const invalidate = useInvalidateFavorites();
  const optimistic = useOptimisticToggle(() => false);
  return useMutation({
    mutationFn: async (listingId: string) => {
      const result = await api.DELETE('/api/v1/me/favorites/{listing_id}', {
        params: { path: { listing_id: listingId } },
      });
      if (result.error) throw toApiError(result.error);
    },
    onMutate: optimistic.onMutate,
    onError: optimistic.onError,
    onSuccess: invalidate,
  });
}
