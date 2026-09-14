'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface MfaStatus {
  enabled: boolean;
  required: boolean;
}

const STATUS_KEY = ['mfa', 'status'] as const;

export function useMfaStatus() {
  return useQuery<MfaStatus>({
    queryKey: STATUS_KEY,
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/mfa/status');
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: MfaStatus }).data;
    },
  });
}

export function useBeginMfaEnrollment() {
  return useMutation({
    mutationFn: async () => {
      const result = await api.POST('/api/v1/me/mfa/enroll');
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: { secret: string; provisioningUri: string } }).data;
    },
  });
}

export function useConfirmMfaEnrollment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (code: string) => {
      const result = await api.POST('/api/v1/me/mfa/confirm', { body: { code } });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: { recoveryCodes: string[] } }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: STATUS_KEY }),
  });
}

export function useDisableMfa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (password: string) => {
      const result = await api.POST('/api/v1/me/mfa/disable', { body: { password } });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: STATUS_KEY }),
  });
}
