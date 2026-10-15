/** Feature state, queries or side-effect coordination for use seller search. */
'use client';

import { api } from '@/lib/api/client';
import { useQuery } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export type SellerRisk = 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN';

export interface AdminSeller {
  id: string;
  handle: string;
  displayName: string;
  email: string;
  city: string | null;
  identityStatus: string;
  phoneStatus: string;
  emailStatus: string;
  isFlagged: boolean;
  score: number | null;
  riskLevel: SellerRisk | null;
  updatedAt: string;
}

export interface SellerSearchParams {
  search: string;
  riskLevel: SellerRisk | 'ALL';
  flagged: 'ALL' | 'TRUE' | 'FALSE';
  page: number;
}

interface SellerSearchResponse {
  data: AdminSeller[];
  meta: {
    pagination?: {
      page: number;
      perPage: number;
      total: number;
      totalPages: number;
      hasNext: boolean;
      hasPrev: boolean;
    };
  };
}

export const SELLER_SEARCH_KEY = ['admin', 'sellers'] as const;

export function useSellerSearch(params: SellerSearchParams) {
  return useQuery({
    queryKey: [...SELLER_SEARCH_KEY, params],
    queryFn: async (): Promise<SellerSearchResponse> => {
      const query = {
        ...(params.search ? { search: params.search } : {}),
        ...(params.riskLevel !== 'ALL' ? { riskLevel: params.riskLevel } : {}),
        ...(params.flagged !== 'ALL' ? { flagged: params.flagged === 'TRUE' } : {}),
        page: params.page,
        perPage: 20,
      };
      const result = await api.GET('/api/v1/admin/sellers', {
        params: {
          query,
        },
      });
      if (result.error) throw toApiError(result.error);
      return result.data as unknown as SellerSearchResponse;
    },
    placeholderData: (previous) => previous,
  });
}
