'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export type OfferStatus = 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'COUNTERED' | 'EXPIRED';
export type TransactionStatus =
  | 'INITIATED'
  | 'AGREED'
  | 'MEETUP_PLANNED'
  | 'HANDED_OVER'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'DISPUTED';

export interface Offer {
  id: string;
  conversationId: string;
  listingId: string;
  buyerId: string;
  sellerId: string;
  offeredBy: string;
  amount: number;
  currency: string;
  status: OfferStatus;
  createdAt: string;
  expiresAt: string;
  message: string | null;
  parentOfferId: string | null;
  respondedAt: string | null;
}

export interface Transaction {
  id: string;
  listingId: string;
  buyerId: string;
  sellerId: string;
  offerId: string;
  amount: number;
  currency: string;
  status: TransactionStatus;
  createdAt: string;
  updatedAt: string | null;
  completedAt: string | null;
  cancelledAt: string | null;
  cancelReason: string | null;
}

const qk = {
  offers: (conversationId: string) => ['commerce', 'offers', conversationId] as const,
  myTransactions: ['commerce', 'my-transactions'] as const,
};

export function useOffers(conversationId: string | null) {
  return useQuery<Offer[]>({
    queryKey: qk.offers(conversationId ?? 'none'),
    enabled: Boolean(conversationId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/conversations/{conversation_id}/offers', {
        params: { path: { conversation_id: conversationId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Offer[] }).data;
    },
    refetchInterval: 8_000,
  });
}

export function useCreateOffer(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { amount: number; message?: string; ttlHours?: number }) => {
      const result = await api.POST('/api/v1/conversations/{conversation_id}/offers', {
        params: { path: { conversation_id: conversationId } },
        body: {
          amount: input.amount,
          currency: 'PKR',
          message: input.message ?? null,
          ttlHours: input.ttlHours ?? 48,
        },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Offer }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.offers(conversationId) }),
  });
}

export function useRespondToOffer(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { offerId: string; accept: boolean }) => {
      const result = await api.POST('/api/v1/offers/{offer_id}/respond', {
        params: { path: { offer_id: input.offerId } },
        body: { accept: input.accept },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: { offer: Offer; transaction: Transaction | null } })
        .data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: qk.offers(conversationId) });
      await queryClient.invalidateQueries({ queryKey: qk.myTransactions });
    },
  });
}

export function useMyTransactions() {
  return useQuery<Transaction[]>({
    queryKey: qk.myTransactions,
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/transactions');
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Transaction[] }).data;
    },
  });
}

export function useConfirmHandover() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (transactionId: string) => {
      const result = await api.POST('/api/v1/transactions/{transaction_id}/handover', {
        params: { path: { transaction_id: transactionId } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Transaction }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.myTransactions }),
  });
}

export function useCompleteTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (transactionId: string) => {
      const result = await api.POST('/api/v1/transactions/{transaction_id}/complete', {
        params: { path: { transaction_id: transactionId } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Transaction }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.myTransactions }),
  });
}

export function useCancelTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { transactionId: string; reason: string }) => {
      const result = await api.POST('/api/v1/transactions/{transaction_id}/cancel', {
        params: { path: { transaction_id: input.transactionId } },
        body: { reason: input.reason },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Transaction }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.myTransactions }),
  });
}
