'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body: string;
  data: Record<string, string>;
  createdAt: string;
  readAt: string | null;
}

const qk = { list: ['notifications'] as const };

/**
 * Polled, not pushed - the same reasoning as messaging (see its hook):
 * a real-time channel is infrastructure this product doesn't have yet,
 * and a periodic poll is indistinguishable from push for a notification
 * bell nobody is staring at continuously.
 */
export function useNotifications(enabled = true) {
  return useQuery<{ items: AppNotification[]; unreadCount: number }>({
    queryKey: qk.list,
    enabled,
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/notifications', {
        params: { query: { limit: 30 } },
      });
      if (result.error) throw toApiError(result.error);
      const body = result.data as {
        data: AppNotification[];
        meta?: { unreadCount?: number };
      };
      return { items: body.data, unreadCount: body.meta?.unreadCount ?? 0 };
    },
    refetchInterval: 20_000,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (notificationId: string) => {
      const result = await api.PUT('/api/v1/me/notifications/{notification_id}/read', {
        params: { path: { notification_id: notificationId } },
      });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: qk.list });
    },
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const result = await api.PUT('/api/v1/me/notifications/read-all');
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: qk.list });
    },
  });
}
