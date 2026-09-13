'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface Review {
  id: string;
  transactionId: string;
  listingId: string;
  reviewerId: string;
  revieweeId: string;
  rating: number;
  comment: string | null;
  createdAt: string;
}

const qk = {
  myFollows: ['reputation', 'my-follows'] as const,
  myReview: (transactionId: string) => ['reputation', 'my-review', transactionId] as const,
};

export function useMyFollows() {
  return useQuery<string[]>({
    queryKey: qk.myFollows,
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/follows');
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: string[] }).data;
    },
  });
}

export function useFollowSeller() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (handle: string) => {
      const result = await api.POST('/api/v1/me/follows', { body: { handle } });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.myFollows }),
  });
}

export function useUnfollowSeller() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (handle: string) => {
      const result = await api.DELETE('/api/v1/me/follows/{handle}', {
        params: { path: { handle } },
      });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.myFollows }),
  });
}

export function useMyReviewForTransaction(transactionId: string | null) {
  return useQuery<Review | null>({
    queryKey: qk.myReview(transactionId ?? 'none'),
    enabled: Boolean(transactionId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/transactions/{transaction_id}/reviews/mine', {
        params: { path: { transaction_id: transactionId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Review | null }).data;
    },
  });
}

export function useCreateReview(transactionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { rating: number; comment?: string }) => {
      const result = await api.POST('/api/v1/transactions/{transaction_id}/reviews', {
        params: { path: { transaction_id: transactionId } },
        body: { rating: input.rating, comment: input.comment ?? null },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Review }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.myReview(transactionId) }),
  });
}
