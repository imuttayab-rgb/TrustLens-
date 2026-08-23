'use client';

import { api } from '@/lib/api/client';
import { useQuery } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface IdentityReviewDocument {
  documentType: 'CNIC_FRONT' | 'CNIC_BACK' | 'SELFIE';
  status: string;
  previewUrl: string;
  urlExpiresAt: string;
  ocrConfidence: number | null;
  qualityScore: number | null;
  extractedName: string | null;
  expiryDate: string | null;
}

export interface IdentityReview {
  sellerId: string;
  verificationId: string;
  decision: string;
  decisionSource: string;
  faceMatchEngine: string | null;
  faceSimilarity: number | null;
  faceDistance: number | null;
  thresholdUsed: number | null;
  livenessPassed: boolean | null;
  nameMatchScore: number | null;
  decisionReason: string | null;
  documents: IdentityReviewDocument[];
}

export function useIdentityReview(sellerId: string | null, enabled = true) {
  return useQuery<IdentityReview>({
    queryKey: ['admin', 'identity-review', sellerId ?? 'none'],
    enabled: Boolean(sellerId) && enabled,
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/sellers/{seller_id}/identity-review', {
        params: { path: { seller_id: sellerId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: IdentityReview }).data;
    },
  });
}
