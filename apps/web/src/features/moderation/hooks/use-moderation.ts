/** Feature state, queries or side-effect coordination for use moderation. */
'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export type ReportTargetType =
  'LISTING' | 'SELLER' | 'MESSAGE' | 'TRANSACTION' | 'MEETUP' | 'OTHER';
export type ReportCategory =
  'SCAM_OR_FRAUD' | 'PROHIBITED_ITEM' | 'HARASSMENT' | 'MISLEADING_LISTING' | 'OTHER';

export interface Report {
  id: string;
  targetType: ReportTargetType;
  targetId: string;
  category: ReportCategory;
  description: string;
  status: string;
  createdAt: string;
  resolvedAt: string | null;
  resolutionNote: string | null;
}

const qk = {
  myReports: ['moderation', 'my-reports'] as const,
  myBlocks: ['moderation', 'my-blocks'] as const,
};

export function useCreateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      targetType: ReportTargetType;
      targetId: string;
      category: ReportCategory;
      description: string;
    }) => {
      const result = await api.POST('/api/v1/me/reports', { body: input });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Report }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.myReports }),
  });
}

export function useMyReports() {
  return useQuery<Report[]>({
    queryKey: qk.myReports,
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/reports');
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Report[] }).data;
    },
  });
}

export function useMyBlocks() {
  return useQuery<string[]>({
    queryKey: qk.myBlocks,
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/blocks');
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: string[] }).data;
    },
  });
}

export function useBlockUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (blockedUserId: string) => {
      const result = await api.POST('/api/v1/me/blocks', { body: { blockedUserId } });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.myBlocks }),
  });
}

export function useUnblockUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (blockedUserId: string) => {
      const result = await api.DELETE('/api/v1/me/blocks/{blocked_user_id}', {
        params: { path: { blocked_user_id: blockedUserId } },
      });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.myBlocks }),
  });
}
