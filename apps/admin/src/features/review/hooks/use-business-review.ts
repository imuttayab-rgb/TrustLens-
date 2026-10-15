/** Feature state, queries or side-effect coordination for use business review. */
'use client';

import { api } from '@/lib/api/client';
import { useQuery } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface BusinessReview {
  sellerId: string;
  legalName: string | null;
  registrationNumber: string | null;
  status: string;
  previewUrl: string | null;
  urlExpiresAt: string;
}

export function useBusinessReview(sellerId: string | null, enabled = true) {
  return useQuery<BusinessReview | null>({
    queryKey: ['admin', 'business-review', sellerId ?? 'none'],
    enabled: Boolean(sellerId) && enabled,
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/sellers/{seller_id}/business-review', {
        params: { path: { seller_id: sellerId as string } },
      });
      if (result.error) {
        const apiError = toApiError(result.error);
        // No submission yet is a normal state, not an error.
        if (apiError.status === 404) return null;
        throw apiError;
      }
      return (result.data as unknown as { data: BusinessReview }).data;
    },
  });
}
