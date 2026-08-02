'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { useQuery } from '@tanstack/react-query';
import type { RiskLevel, VerificationStatus } from '@trustlens/constants';

export interface SellerProfile {
  id: string;
  handle: string;
  displayName: string;
  city: string | null;
  identityStatus: VerificationStatus;
  phoneStatus: VerificationStatus;
  emailStatus: VerificationStatus;
  isFlagged: boolean;
  score: number | null;
  riskLevel: RiskLevel | null;
}

export interface ChecklistItem {
  key: string;
  label: string;
  status: VerificationStatus;
  pointsAvailable: number;
  actionUrl: string | null;
}

export interface VerificationSummary {
  identity: VerificationStatus;
  phone: VerificationStatus;
  email: VerificationStatus;
  device: VerificationStatus;
  checklist: ChecklistItem[];
}

/** Null means "signed in but has no seller profile yet", not an error. */
export function useSeller() {
  return useQuery<SellerProfile | null>({
    queryKey: qk.seller.me,
    queryFn: async () => {
      const result = await api.GET('/api/v1/sellers/me');
      if (result.error) return null;
      return (result.data as { data: SellerProfile }).data;
    },
    retry: false,
  });
}

export function useVerificationStatus() {
  return useQuery<VerificationSummary | null>({
    queryKey: qk.verification.status,
    queryFn: async () => {
      const result = await api.GET('/api/v1/verification/status');
      if (result.error) return null;
      return (result.data as { data: VerificationSummary }).data;
    },
    retry: false,
  });
}
