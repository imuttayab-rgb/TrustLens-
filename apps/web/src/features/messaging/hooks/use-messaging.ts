'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface ConversationSummary {
  id: string;
  listingId: string | null;
  listingTitle: string | null;
  counterpartName: string;
  lastMessageAt: string;
  lastMessagePreview: string | null;
  unreadCount: number;
  createdAt: string;
}

export interface Message {
  id: string;
  conversationId: string;
  senderId: string;
  body: string;
  createdAt: string;
  readAt: string | null;
}

const qk = {
  conversations: ['conversations'] as const,
  messages: (conversationId: string) => ['conversations', conversationId, 'messages'] as const,
};

export function useConversations() {
  return useQuery<{ items: ConversationSummary[]; total: number }>({
    queryKey: qk.conversations,
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/conversations');
      if (result.error) throw toApiError(result.error);
      const body = result.data as {
        data: ConversationSummary[];
        meta?: { pagination?: { total: number } };
      };
      return { items: body.data, total: body.meta?.pagination?.total ?? body.data.length };
    },
    // A short poll, not a websocket - see the backend use-case docstring for
    // why. Frequent enough that a reply feels prompt, cheap enough that it
    // costs nothing to leave an inbox tab open.
    refetchInterval: 8_000,
  });
}

export function useMessages(conversationId: string | null) {
  return useQuery<Message[]>({
    queryKey: qk.messages(conversationId ?? 'none'),
    enabled: Boolean(conversationId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/conversations/{conversation_id}/messages', {
        params: { path: { conversation_id: conversationId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: Message[] }).data;
    },
    refetchInterval: 5_000,
  });
}

export function useSendMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { body: string; conversationId?: string; listingId?: string }) => {
      const result = await api.POST('/api/v1/me/conversations', {
        body: {
          body: input.body,
          conversationId: input.conversationId ?? null,
          listingId: input.listingId ?? null,
        },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: { conversationId: string; message: Message } }).data;
    },
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: qk.conversations });
      await queryClient.invalidateQueries({ queryKey: qk.messages(data.conversationId) });
    },
  });
}
