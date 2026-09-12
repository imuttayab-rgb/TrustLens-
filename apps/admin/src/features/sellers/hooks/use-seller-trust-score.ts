'use client';

import { api } from '@/lib/api/client';
import { useQuery } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import type { RiskLevel, SignalCategory, SignalStatus } from '@trustlens/constants';

export interface SellerTrustScoreSignal {
  code: string;
  category: SignalCategory;
  status: SignalStatus;
  pointsAwarded: number;
  pointsPossible: number;
  confidence: number;
  reasonCode: string;
  reasonText: string;
}

export interface SellerTrustScoreDetail {
  id: string;
  sellerId: string;
  score: number;
  riskLevel: RiskLevel;
  confidence: number;
  modelVersion: string;
  computedAt: string;
  capApplied: number | null;
  summary: string;
  signals: SellerTrustScoreSignal[];
}

/**
 * Admin-side read of the same per-signal breakdown a seller sees on their
 * own dashboard - `GET /admin/sellers/{id}/trust-score`, gated on
 * trust_score:read:full rather than the seller-facing route, so this stays
 * a routed, auditable grant instead of piggybacking on seller:read:any.
 */
export function useSellerTrustScore(sellerId: string) {
  return useQuery<SellerTrustScoreDetail | null>({
    queryKey: ['admin', 'seller', sellerId, 'trust-score'],
    enabled: Boolean(sellerId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/sellers/{seller_id}/trust-score', {
        params: { path: { seller_id: sellerId } },
      });
      // A seller with no score yet is a normal state (identity/phone/email
      // checks not done), not an error - render "not scored yet" instead.
      if (result.error) {
        const apiError = toApiError(result.error);
        if (apiError.status === 404) return null;
        throw apiError;
      }
      return (result.data as unknown as { data: SellerTrustScoreDetail }).data;
    },
  });
}
