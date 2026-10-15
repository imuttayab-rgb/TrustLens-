/** Feature state, queries or side-effect coordination for use commerce. */
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

export function useRaiseDispute() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { transactionId: string; category: string; description: string }) => {
      const result = await api.POST('/api/v1/transactions/{transaction_id}/dispute', {
        params: { path: { transaction_id: input.transactionId } },
        body: { category: input.category, description: input.description },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Transaction }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.myTransactions }),
  });
}

// ── Installments (PAY-01) - a payment schedule, not a payment processor;
// see the backend use-case module for why "sandbox" is the honest word. ──

export type InstallmentPlanStatus = 'ACTIVE' | 'COMPLETED' | 'CANCELLED';
export type InstallmentStatus = 'PENDING' | 'PAID';

export interface Installment {
  id: string;
  sequenceNumber: number;
  amount: number;
  dueAt: string;
  status: InstallmentStatus;
  paidAt: string | null;
  paidBy: string | null;
}

export interface InstallmentPlan {
  id: string;
  transactionId: string;
  buyerId: string;
  sellerId: string;
  totalAmount: number;
  currency: string;
  installmentCount: number;
  status: InstallmentPlanStatus;
  createdAt: string;
  cancelledAt: string | null;
  installments: Installment[];
}

const commerceQk = {
  installmentPlan: (transactionId: string) =>
    ['commerce', 'installment-plan', transactionId] as const,
  auction: (auctionId: string) => ['commerce', 'auction', auctionId] as const,
  auctionBids: (auctionId: string) => ['commerce', 'auction', auctionId, 'bids'] as const,
};

export function useInstallmentPlan(transactionId: string | null) {
  return useQuery<InstallmentPlan | null>({
    queryKey: commerceQk.installmentPlan(transactionId ?? 'none'),
    enabled: Boolean(transactionId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/transactions/{transaction_id}/installment-plan', {
        params: { path: { transaction_id: transactionId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: InstallmentPlan | null }).data;
    },
  });
}

export function useCreateInstallmentPlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      transactionId: string;
      installmentCount: number;
      frequencyDays: number;
    }) => {
      const result = await api.POST('/api/v1/transactions/{transaction_id}/installment-plan', {
        params: { path: { transaction_id: input.transactionId } },
        body: { installmentCount: input.installmentCount, frequencyDays: input.frequencyDays },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: InstallmentPlan }).data;
    },
    onSuccess: async (_data, input) => {
      await queryClient.invalidateQueries({
        queryKey: commerceQk.installmentPlan(input.transactionId),
      });
      await queryClient.invalidateQueries({ queryKey: qk.myTransactions });
    },
  });
}

export function usePayInstallment(transactionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (installmentId: string) => {
      const result = await api.POST('/api/v1/installments/{installment_id}/pay', {
        params: { path: { installment_id: installmentId } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Installment }).data;
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: commerceQk.installmentPlan(transactionId) }),
  });
}

export function useCancelInstallmentPlan(transactionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (planId: string) => {
      const result = await api.POST('/api/v1/installment-plans/{plan_id}/cancel', {
        params: { path: { plan_id: planId } },
      });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: commerceQk.installmentPlan(transactionId) }),
  });
}

// ── Auctions (AUC-01) ─────────────────────────────────────────────────

export type AuctionStatus = 'ACTIVE' | 'ENDED' | 'CANCELLED';

export interface Auction {
  id: string;
  listingId: string;
  sellerId: string;
  startingPrice: number;
  currency: string;
  endsAt: string;
  status: AuctionStatus;
  createdAt: string;
  reservePrice: number | null;
  winningBidId: string | null;
  endedAt: string | null;
  currentPrice: number | null;
  bidCount: number;
}

export interface Bid {
  id: string;
  auctionId: string;
  bidderId: string;
  amount: number;
  createdAt: string;
}

export function useCreateAuction(listingId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      startingPrice: number;
      currency?: string;
      durationHours: number;
      reservePrice?: number;
    }) => {
      const result = await api.POST('/api/v1/listings/{listing_id}/auction', {
        params: { path: { listing_id: listingId } },
        body: {
          startingPrice: input.startingPrice,
          currency: input.currency ?? 'PKR',
          durationHours: input.durationHours,
          reservePrice: input.reservePrice ?? null,
        },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Auction }).data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(commerceQk.auction(data.id), data);
      queryClient.setQueryData(['commerce', 'listing-auction', listingId] as const, data);
    },
  });
}

export function useAuctionForListing(listingId: string | null) {
  return useQuery<Auction | null>({
    queryKey: ['commerce', 'listing-auction', listingId ?? 'none'] as const,
    enabled: Boolean(listingId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/listings/{listing_id}/auction', {
        params: { path: { listing_id: listingId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Auction | null }).data;
    },
    refetchInterval: 10_000,
  });
}

export function useAuction(auctionId: string | null) {
  return useQuery<Auction | null>({
    queryKey: commerceQk.auction(auctionId ?? 'none'),
    enabled: Boolean(auctionId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/auctions/{auction_id}', {
        params: { path: { auction_id: auctionId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Auction }).data;
    },
    refetchInterval: 10_000,
  });
}

export function useAuctionBids(auctionId: string | null) {
  return useQuery<Bid[]>({
    queryKey: commerceQk.auctionBids(auctionId ?? 'none'),
    enabled: Boolean(auctionId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/auctions/{auction_id}/bids', {
        params: { path: { auction_id: auctionId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Bid[] }).data;
    },
    refetchInterval: 10_000,
  });
}

export function usePlaceBid(auctionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (amount: number) => {
      const result = await api.POST('/api/v1/auctions/{auction_id}/bids', {
        params: { path: { auction_id: auctionId } },
        body: { amount },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Bid }).data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: commerceQk.auction(auctionId) });
      await queryClient.invalidateQueries({ queryKey: commerceQk.auctionBids(auctionId) });
    },
  });
}
