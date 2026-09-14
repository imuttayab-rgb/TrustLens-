'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface ReviewCase {
  id: string;
  seller_id: string;
  case_type:
    'IDENTITY_REVIEW' | 'FRAUD_FLAG' | 'APPEAL' | 'DEVICE_CLUSTER' | 'BUSINESS_VERIFICATION';
  status: 'QUEUED' | 'ASSIGNED' | 'APPROVED' | 'REJECTED' | 'ESCALATED';
  priority: number;
  created_at: string;
  trigger_reason: string | null;
  related_entity_type: string | null;
  related_entity_id: string | null;
  assigned_to: string | null;
  decision: string | null;
  decision_note: string | null;
}

export const QUEUE_KEY = ['admin', 'review-cases'] as const;

export function useReviewQueue() {
  return useQuery<ReviewCase[]>({
    queryKey: QUEUE_KEY,
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/review-cases');
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: ReviewCase[] }).data;
    },
    // A reviewer works from this list; a stale queue means two people opening
    // the same case.
    refetchInterval: 30_000,
    staleTime: 0,
  });
}

function useRefreshQueue() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: QUEUE_KEY });
}

export function useClaimCase() {
  const refresh = useRefreshQueue();
  return useMutation({
    mutationFn: async (caseId: string) => {
      const result = await api.POST('/api/v1/admin/review-cases/{case_id}/claim', {
        params: { path: { case_id: caseId } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: ReviewCase }).data;
    },
    onSuccess: refresh,
  });
}

export function useDecideCase() {
  const refresh = useRefreshQueue();
  return useMutation({
    mutationFn: async ({
      caseId,
      approve,
      note,
    }: {
      caseId: string;
      approve: boolean;
      note: string;
    }) => {
      const result = await api.POST('/api/v1/admin/review-cases/{case_id}/decide', {
        params: { path: { case_id: caseId } },
        body: { approve, note },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: { case: ReviewCase; identityUpdated: boolean } }).data;
    },
    onSuccess: refresh,
  });
}

export { useIdentityReview } from './use-identity-review';
export type { IdentityReview, IdentityReviewDocument } from './use-identity-review';
export { useBusinessReview } from './use-business-review';
export type { BusinessReview } from './use-business-review';
