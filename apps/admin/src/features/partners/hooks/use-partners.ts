'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export type PartnerStatus = 'PENDING' | 'ACTIVE' | 'SUSPENDED';

export interface Partner {
  id: string;
  name: string;
  slug: string;
  contactEmail: string;
  status: PartnerStatus;
  rateLimitTier: string;
  monthlyQuota: number;
  usedThisMonth: number;
  remaining: number;
  percentUsed: number;
  createdAt: string;
}

export interface ApiKey {
  id: string;
  name: string;
  /** The lookup half. The secret half is shown once, at creation, and never again. */
  keyPrefix: string;
  scopes: string[];
  status: string;
  /** Human-readable: active | revoked | expired | expires <date>. */
  state: string;
  createdAt: string;
  lastUsedAt: string | null;
  expiresAt: string | null;
}

export interface IssuedKey {
  key: ApiKey;
  /**
   * The only copy of the key that will ever exist. Held in component state
   * for as long as the dialog is open and never written to a query cache -
   * a cached credential is one `staleTime` away from being logged.
   */
  plaintext: string;
}

export const PARTNERS_KEY = ['admin', 'partners'] as const;
export const partnerKeysKey = (clientId: string) =>
  ['admin', 'partners', clientId, 'keys'] as const;

export function usePartners() {
  return useQuery<Partner[]>({
    queryKey: PARTNERS_KEY,
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/partners');
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: Partner[] }).data;
    },
  });
}

export function usePartnerKeys(clientId: string | null) {
  return useQuery<ApiKey[]>({
    queryKey: partnerKeysKey(clientId ?? 'none'),
    enabled: Boolean(clientId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/partners/{client_id}/keys', {
        params: { path: { client_id: clientId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: ApiKey[] }).data;
    },
  });
}

export function useScopes() {
  return useQuery<string[]>({
    queryKey: ['admin', 'partners', 'scopes'],
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/partners/scopes');
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: string[] }).data;
    },
    // The scope vocabulary changes when the API does, not during a session.
    staleTime: Infinity,
  });
}

function useRefreshPartners() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: PARTNERS_KEY });
}

export function useRegisterPartner() {
  const refresh = useRefreshPartners();
  return useMutation({
    mutationFn: async (input: {
      name: string;
      slug: string;
      contactEmail: string;
      monthlyQuota: number;
    }) => {
      const result = await api.POST('/api/v1/admin/partners', {
        // `rateLimitTier` has a server-side default but is required by the
        // generated type: a Pydantic default does not make a field optional
        // in the OpenAPI schema. Sent explicitly rather than cast away.
        body: { ...input, rateLimitTier: 'free' },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: Partner }).data;
    },
    onSuccess: refresh,
  });
}

export function useSetPartnerStatus() {
  const refresh = useRefreshPartners();
  return useMutation({
    mutationFn: async (input: { clientId: string; status: PartnerStatus }) => {
      const result = await api.POST('/api/v1/admin/partners/{client_id}/status', {
        params: { path: { client_id: input.clientId } },
        body: { status: input.status },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: Partner }).data;
    },
    onSuccess: refresh,
  });
}

function useRefreshKeys(clientId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: partnerKeysKey(clientId) });
}

export function useIssueKey(clientId: string) {
  const refresh = useRefreshKeys(clientId);
  return useMutation({
    mutationFn: async (input: { name: string; scopes: string[]; expiresInDays: number | null }) => {
      const result = await api.POST('/api/v1/admin/partners/{client_id}/keys', {
        params: { path: { client_id: clientId } },
        body: {
          name: input.name,
          scopes: input.scopes,
          expiresInDays: input.expiresInDays,
        },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: IssuedKey }).data;
    },
    onSuccess: refresh,
  });
}

export function useRotateKey(clientId: string) {
  const refresh = useRefreshKeys(clientId);
  return useMutation({
    mutationFn: async (keyId: string) => {
      const result = await api.POST('/api/v1/admin/partners/keys/{key_id}/rotate', {
        params: { path: { key_id: keyId } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: IssuedKey }).data;
    },
    onSuccess: refresh,
  });
}

export function useRevokeKey(clientId: string) {
  const refresh = useRefreshKeys(clientId);
  return useMutation({
    mutationFn: async (keyId: string) => {
      const result = await api.DELETE('/api/v1/admin/partners/keys/{key_id}', {
        params: { path: { key_id: keyId } },
      });
      if (result.error) throw toApiError(result.error);
      return true;
    },
    onSuccess: refresh,
  });
}
