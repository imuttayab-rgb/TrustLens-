'use client';

import { api } from '@/lib/api/client';
import { useQuery } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import type { AdminSeller, SellerRisk } from './use-seller-search';

export interface SellerScoreHistory {
  id: string;
  score: number;
  riskLevel: SellerRisk;
  modelVersion: string;
  trigger: string;
  computedAt: string;
  manualOverride: boolean;
}

export interface AdminSellerDetail extends AdminSeller {
  scoreHistory: SellerScoreHistory[];
}

export function useSellerDetail(sellerId: string) {
  return useQuery<AdminSellerDetail>({
    queryKey: ['admin', 'seller', sellerId],
    enabled: Boolean(sellerId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/sellers/{seller_id}', {
        params: { path: { seller_id: sellerId } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: AdminSellerDetail }).data;
    },
  });
}
