'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export type ReportTargetType = 'LISTING' | 'SELLER' | 'MESSAGE' | 'OTHER';
export type ReportCategory =
  'SCAM_OR_FRAUD' | 'PROHIBITED_ITEM' | 'HARASSMENT' | 'MISLEADING_LISTING' | 'OTHER';
export type ReportStatus = 'OPEN' | 'UNDER_REVIEW' | 'RESOLVED' | 'DISMISSED';

export interface AdminReport {
  id: string;
  reporterId: string;
  targetType: ReportTargetType;
  targetId: string;
  category: ReportCategory;
  description: string;
  status: ReportStatus;
  createdAt: string;
  resolvedAt: string | null;
  resolvedBy: string | null;
  resolutionNote: string | null;
}

const REPORTS_KEY = ['admin', 'reports'] as const;

export function useReportQueue(status?: ReportStatus) {
  return useQuery<{ items: AdminReport[]; total: number }>({
    queryKey: [...REPORTS_KEY, status ?? 'ALL'],
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/reports', {
        params: { query: { status: status ?? null, limit: 50 } },
      });
      if (result.error) throw toApiError(result.error);
      const body = result.data as unknown as {
        data: AdminReport[];
        meta?: { pagination?: { total: number } };
      };
      return { items: body.data, total: body.meta?.pagination?.total ?? body.data.length };
    },
    refetchInterval: 30_000,
  });
}

export function useResolveReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      reportId,
      status,
      resolutionNote,
    }: {
      reportId: string;
      status: 'RESOLVED' | 'DISMISSED';
      resolutionNote: string;
    }) => {
      const result = await api.POST('/api/v1/admin/reports/{report_id}/resolve', {
        params: { path: { report_id: reportId } },
        // This request body is plain snake_case (ResolveReportRequest is a
        // bare BaseModel in admin.py, unlike the camelCase Schema-based
        // response models this file otherwise deals with).
        body: { status, resolution_note: resolutionNote },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: AdminReport }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: REPORTS_KEY }),
  });
}
