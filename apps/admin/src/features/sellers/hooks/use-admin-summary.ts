/** Feature state, queries or side-effect coordination for use admin summary. */
'use client';

import { api } from '@/lib/api/client';
import { useQuery } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface AdminSummary {
  totalSellers: number;
  lowRisk: number;
  mediumRisk: number;
  highRisk: number;
  unknownRisk: number;
  flagged: number;
}

export function useAdminSummary() {
  return useQuery<AdminSummary>({
    queryKey: ['admin', 'dashboard-summary'],
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/dashboard/summary');
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: AdminSummary }).data;
    },
    refetchInterval: 30_000,
  });
}
