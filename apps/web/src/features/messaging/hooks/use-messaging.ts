/** Feature state, queries or side-effect coordination for use messaging. */
'use client';

import { profileRequest } from '@/features/profile';
import { api } from '@/lib/api/client';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface ConversationSummary {
  id: string;
  listingId: string | null;
  listingTitle: string | null;
  counterpartName: string;
  counterpartUserId: string;
  counterpartProfileUrl?: string;
  counterpartAvatarUrl?: string | null;
  counterpartPhotoMatched?: boolean;
  lastMessageAt: string;
  lastMessagePreview: string | null;
  unreadCount: number;
  createdAt: string;
  muted: boolean;
  important?: boolean;
  serverNow?: string;
  listingStatus?: string;
  inactiveSince?: string | null;
  closesAt?: string | null;
  readOnly?: boolean;
  canSend?: boolean;
  blocked?: boolean;
  /** Only set when the counterpart is the seller side (i.e. the current
   * user is the buyer here) - a buyer counterpart has no trust score. */
  counterpartSellerHandle: string | null;
  counterpartRiskLevel: string | null;
  counterpartScore: number | null;
}

export interface Message {
  id: string;
  conversationId: string;
  senderId: string;
  body: string;
  createdAt: string;
  readAt: string | null;
  kind?: 'text' | 'voice';
  playedAt?: string | null;
  editedAt?: string | null;
  deleted?: boolean;
  editableUntil?: string;
  replyTo?: { id: string; body: string } | null;
  forwarded?: boolean;
  voice?: { duration: number; waveform: number[] } | null;
}

const qk = {
  conversations: ['conversations'] as const,
  messages: (conversationId: string) => ['conversations', conversationId, 'messages'] as const,
};

export function useConversations(
  options: {
    folder?: 'all' | 'buying' | 'selling' | 'unread' | 'important';
    q?: string;
    offset?: number;
    limit?: number;
  } = {},
) {
  return useQuery<{ items: ConversationSummary[]; total: number }>({
    queryKey: [...qk.conversations, options],
    queryFn: async () => {
      const result = await api.GET('/api/v1/me/conversations', { params: { query: options } });
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
  const query = useInfiniteQuery({
    queryKey: qk.messages(conversationId ?? 'none'),
    enabled: Boolean(conversationId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      profileRequest<{ items: Message[]; nextCursor: string | null; serverNow: string }>(
        `/me/conversations/${conversationId}/timeline${pageParam ? `?before=${pageParam}` : ''}`,
      ),
    getNextPageParam: (page) => page.nextCursor,
    refetchInterval: 5_000,
  });
  return {
    ...query,
    data: query.data?.pages
      .slice()
      .reverse()
      .flatMap((page) => page.items),
    serverNow: query.data?.pages[0]?.serverNow,
  };
}

export function useSendMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      body: string;
      conversationId?: string;
      listingId?: string;
      clientId?: string;
      replyToId?: string;
      forwardId?: string;
    }) =>
      profileRequest<{ conversationId: string; message: Message }>('/me/conversations', {
        method: 'POST',
        body: JSON.stringify({ ...input, clientId: input.clientId ?? crypto.randomUUID() }),
      }),
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: qk.conversations });
      await queryClient.invalidateQueries({ queryKey: qk.messages(data.conversationId) });
    },
  });
}

export function useSetConversationMuted() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { conversationId: string; muted: boolean }) => {
      const result = await api.PUT('/api/v1/me/conversations/{conversation_id}/muted', {
        params: { path: { conversation_id: input.conversationId } },
        body: { muted: input.muted },
      });
      if (result.error) throw toApiError(result.error);
      return input;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: qk.conversations });
    },
  });
}

export function useConversation(conversationId: string) {
  return useQuery<ConversationSummary>({
    queryKey: ['conversations', conversationId, 'header'],
    queryFn: () => profileRequest(`/me/conversations/${encodeURIComponent(conversationId)}`),
    staleTime: 2_000,
    refetchInterval: 5_000,
    retry: 1,
  });
}

export function useSetConversationImportant() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { conversationId: string; important: boolean }) =>
      profileRequest<{ important: boolean }>(
        `/me/conversations/${input.conversationId}/important`,
        { method: 'PUT', body: JSON.stringify({ important: input.important }) },
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: qk.conversations }),
  });
}
