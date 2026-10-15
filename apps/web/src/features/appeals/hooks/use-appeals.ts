/** Feature state, queries or side-effect coordination for use appeals. */
'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export type AppealStatus =
  'OPEN' | 'UNDER_REVIEW' | 'NEEDS_INFO' | 'APPROVED' | 'REJECTED' | 'WITHDRAWN';

export type AppealReasonCategory =
  'IDENTITY_INCORRECT' | 'PHONE_INCORRECT' | 'LISTING_MISJUDGED' | 'DEVICE_INCORRECT' | 'OTHER';

export interface AppealMessage {
  id: string;
  senderId: string;
  senderRole: string;
  body: string;
  createdAt: string;
  isInternal: boolean;
}

export interface Appeal {
  id: string;
  sellerId: string;
  trustScoreId: string;
  reasonCategory: AppealReasonCategory;
  reason: string;
  status: AppealStatus;
  submittedAt: string;
  assignedTo: string | null;
  decision: string | null;
  resolutionNote: string | null;
  resolvedAt: string | null;
  messages: AppealMessage[];
}

/** Statuses a reviewer can still act on. Everything else is history. */
export const OPEN_APPEAL_STATUSES: readonly AppealStatus[] = ['OPEN', 'UNDER_REVIEW', 'NEEDS_INFO'];

export function isOpen(appeal: Appeal): boolean {
  return OPEN_APPEAL_STATUSES.includes(appeal.status);
}

export function useMyAppeals() {
  return useQuery<Appeal[]>({
    queryKey: qk.appeal.mine,
    queryFn: async () => {
      const result = await api.GET('/api/v1/appeals');
      // A buyer with no seller profile has no appeals rather than an error,
      // and the score page renders for them too.
      if (result.error) return [];
      return (result.data as { data: Appeal[] }).data;
    },
    retry: false,
  });
}

export function useSubmitAppeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      sellerId: string;
      trustScoreId: string;
      reasonCategory: AppealReasonCategory;
      reason: string;
    }) => {
      // Re-read the current score id immediately before submitting.
      //
      // Only the live computation can be appealed, and a score is recomputed
      // on every signal change - so a page left open while a verification
      // finishes holds a superseded id. Submitting it earns "your score has
      // been recomputed since this one", which is true, useless, and
      // unactionable: the seller is objecting to the same verdict either way.
      // One extra GET turns a dead end into a submission.
      const fresh = await api.GET('/api/v1/sellers/{seller_id}/trust-score', {
        params: { path: { seller_id: input.sellerId } },
      });
      const currentId = fresh.error
        ? input.trustScoreId
        : ((fresh.data as { data: { id: string } }).data.id ?? input.trustScoreId);

      const result = await api.POST('/api/v1/appeals', {
        body: {
          trustScoreId: currentId,
          reasonCategory: input.reasonCategory,
          reason: input.reason,
        },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: Appeal }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.appeal.mine }),
  });
}

export function useWithdrawAppeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (appealId: string) => {
      const result = await api.POST('/api/v1/appeals/{appeal_id}/withdraw', {
        params: { path: { appeal_id: appealId } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: Appeal }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.appeal.mine }),
  });
}

export function useReplyToAppeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { appealId: string; body: string }) => {
      const result = await api.POST('/api/v1/appeals/{appeal_id}/messages', {
        params: { path: { appeal_id: input.appealId } },
        // Sent explicitly rather than relying on the server default: the
        // generated type marks it required (it has a default, not a null
        // union), and a seller note is never internal - the API refuses one
        // that claims to be.
        body: { body: input.body, isInternal: false },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: AppealMessage }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.appeal.mine }),
  });
}
