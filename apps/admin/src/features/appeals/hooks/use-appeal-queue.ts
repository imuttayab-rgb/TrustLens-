/** Feature state, queries or side-effect coordination for use appeal queue. */
'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export type AppealStatus =
  'OPEN' | 'UNDER_REVIEW' | 'NEEDS_INFO' | 'APPROVED' | 'REJECTED' | 'WITHDRAWN';

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
  reasonCategory: string;
  reason: string;
  status: AppealStatus;
  submittedAt: string;
  assignedTo: string | null;
  decision: string | null;
  resolutionNote: string | null;
  resolvedAt: string | null;
  messages: AppealMessage[];
}

/**
 * RECOMPUTE is the honest default: the evidence was corrected, so the engine
 * runs again and the number follows from it. OVERRIDE writes a number a human
 * chose, which is why it is admin-only and expires.
 */
export type AppealDecision = 'RECOMPUTE' | 'OVERRIDE' | 'REJECT';

export const APPEAL_QUEUE_KEY = ['admin', 'appeals'] as const;

export function useAppealQueue() {
  return useQuery<Appeal[]>({
    queryKey: APPEAL_QUEUE_KEY,
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/appeals');
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: Appeal[] }).data;
    },
    // Two reviewers opening the same appeal is the failure claiming exists to
    // prevent; a stale list makes it likelier.
    refetchInterval: 30_000,
    staleTime: 0,
  });
}

function useRefreshQueue() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: APPEAL_QUEUE_KEY });
}

export function useClaimAppeal() {
  const refresh = useRefreshQueue();
  return useMutation({
    mutationFn: async (appealId: string) => {
      const result = await api.POST('/api/v1/admin/appeals/{appeal_id}/claim', {
        params: { path: { appeal_id: appealId } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: Appeal }).data;
    },
    onSuccess: refresh,
  });
}

export function useAppealMessage() {
  const refresh = useRefreshQueue();
  return useMutation({
    mutationFn: async (input: { appealId: string; body: string; isInternal: boolean }) => {
      const result = await api.POST('/api/v1/admin/appeals/{appeal_id}/messages', {
        params: { path: { appeal_id: input.appealId } },
        body: { body: input.body, isInternal: input.isInternal },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: AppealMessage }).data;
    },
    onSuccess: refresh,
  });
}

export function useResolveAppeal() {
  const refresh = useRefreshQueue();
  return useMutation({
    mutationFn: async (input: {
      appealId: string;
      decision: AppealDecision;
      note: string;
      overrideScore?: number;
    }) => {
      const result = await api.POST('/api/v1/admin/appeals/{appeal_id}/resolve', {
        params: { path: { appeal_id: input.appealId } },
        body: {
          decision: input.decision,
          note: input.note,
          // Only meaningful for OVERRIDE; null rather than omitted so the
          // field is explicit in the request the reviewer's action produced.
          overrideScore: input.overrideScore ?? null,
        },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: { appeal: Appeal; rescoreQueued: boolean } }).data;
    },
    onSuccess: refresh,
  });
}
