'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export type MeetupStatus = 'PROPOSED' | 'ACCEPTED' | 'DECLINED' | 'CANCELLED';

export interface MeetingVenue {
  id: string;
  name: string;
  address: string;
  city: string;
  area: string | null;
  latitude: number;
  longitude: number;
  isActive: boolean;
  notes: string | null;
  createdAt: string;
}

export interface Meetup {
  id: string;
  conversationId: string;
  listingId: string;
  buyerId: string;
  sellerId: string;
  proposedBy: string;
  venueId: string;
  proposedTime: string;
  status: MeetupStatus;
  createdAt: string;
  message: string | null;
  respondedAt: string | null;
}

const qk = {
  nearbyVenues: (city: string) => ['safemeet', 'venues', city] as const,
  meetups: (conversationId: string) => ['safemeet', 'meetups', conversationId] as const,
};

export function useNearbyVenues(city: string | null) {
  return useQuery<MeetingVenue[]>({
    queryKey: qk.nearbyVenues(city ?? 'none'),
    enabled: Boolean(city),
    queryFn: async () => {
      const result = await api.GET('/api/v1/meeting-venues', {
        params: { query: { city: city as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: MeetingVenue[] }).data;
    },
  });
}

export function useMeetups(conversationId: string | null) {
  return useQuery<Meetup[]>({
    queryKey: qk.meetups(conversationId ?? 'none'),
    enabled: Boolean(conversationId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/conversations/{conversation_id}/meetups', {
        params: { path: { conversation_id: conversationId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Meetup[] }).data;
    },
    refetchInterval: 8_000,
  });
}

export function useProposeMeetup(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { venueId: string; proposedTime: string; message?: string }) => {
      const result = await api.POST('/api/v1/conversations/{conversation_id}/meetups', {
        params: { path: { conversation_id: conversationId } },
        body: {
          venueId: input.venueId,
          proposedTime: input.proposedTime,
          message: input.message ?? null,
        },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Meetup }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.meetups(conversationId) }),
  });
}

export function useRespondToMeetup(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { meetupId: string; accept: boolean }) => {
      const result = await api.POST('/api/v1/meetups/{meetup_id}/respond', {
        params: { path: { meetup_id: input.meetupId } },
        body: { accept: input.accept },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: Meetup }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.meetups(conversationId) }),
  });
}
