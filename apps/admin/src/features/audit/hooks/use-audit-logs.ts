'use client';

import { api } from '@/lib/api/client';
import { useQuery } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface AuditLogEntry {
  id: string;
  action: string;
  entityType: string;
  entityId: string | null;
  actorId: string | null;
  actorType: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip: string | null;
  userAgent: string | null;
  requestId: string | null;
  occurredAt: string;
}

export interface AuditLogParams {
  actorId?: string;
  action?: string;
  entityType?: string;
  limit?: number;
}

interface AuditLogsResponse {
  data: AuditLogEntry[];
  meta: { requestId: string | null; timestamp: string };
}

export const AUDIT_LOG_KEY = ['admin', 'audit-logs'] as const;

export function useAuditLogs(params: AuditLogParams = {}) {
  return useQuery({
    queryKey: [...AUDIT_LOG_KEY, params],
    queryFn: async (): Promise<AuditLogsResponse> => {
      const query: Record<string, string | number> = {
        limit: params.limit ?? 100,
      };
      if (params.actorId) query['actorId'] = params.actorId;
      if (params.action) query['action'] = params.action;
      if (params.entityType) query['entityType'] = params.entityType;

      const result = await api.GET('/api/v1/admin/audit-logs', {
        params: { query },
      });
      if (result.error) throw toApiError(result.error);
      return result.data as unknown as AuditLogsResponse;
    },
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  });
}
