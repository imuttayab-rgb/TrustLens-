'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import type { RiskLevel, VerificationStatus } from '@trustlens/constants';

export interface SellerProfile {
  id: string;
  handle: string;
  displayName: string;
  city: string | null;
  identityStatus: VerificationStatus;
  phoneStatus: VerificationStatus;
  emailStatus: VerificationStatus;
  accountType: 'INDIVIDUAL' | 'BUSINESS';
  businessLegalName: string | null;
  businessRegistrationNumber: string | null;
  businessVerificationStatus: VerificationStatus;
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

/** Switches an existing seller profile between individual and business
 * (BUS-01) - the account-type toggle, separate from actually submitting
 * the registration document for review. */
export function useSetAccountType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (accountType: 'INDIVIDUAL' | 'BUSINESS') => {
      const result = await api.PATCH('/api/v1/sellers/me', { body: { accountType } });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: SellerProfile }).data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: qk.seller.me });
    },
  });
}

export function useSubmitBusinessVerification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      legalName: string;
      registrationNumber: string;
      documentFileId: string;
    }) => {
      const result = await api.POST('/api/v1/verification/business', {
        body: {
          legalName: input.legalName,
          registrationNumber: input.registrationNumber,
          documentFileId: input.documentFileId,
        },
      });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: qk.seller.me });
    },
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
