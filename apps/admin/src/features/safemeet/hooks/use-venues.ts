'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface AdminMeetingVenue {
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

const VENUES_KEY = ['admin', 'meeting-venues'] as const;

export function useMeetingVenues() {
  return useQuery<AdminMeetingVenue[]>({
    queryKey: VENUES_KEY,
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/meeting-venues', {
        params: { query: { limit: 100 } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: AdminMeetingVenue[] }).data;
    },
  });
}

export function useCreateMeetingVenue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      name: string;
      address: string;
      city: string;
      latitude: number;
      longitude: number;
      area?: string;
      notes?: string;
    }) => {
      const result = await api.POST('/api/v1/admin/meeting-venues', {
        // Plain snake_case body - CreateMeetingVenueRequest in admin.py is a
        // bare BaseModel, same split as ResolveReportRequest.
        body: {
          name: input.name,
          address: input.address,
          city: input.city,
          latitude: input.latitude,
          longitude: input.longitude,
          area: input.area ?? null,
          notes: input.notes ?? null,
        },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: AdminMeetingVenue }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: VENUES_KEY }),
  });
}

export function useSetVenueActive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ venueId, isActive }: { venueId: string; isActive: boolean }) => {
      const path = isActive
        ? ('/api/v1/admin/meeting-venues/{venue_id}/activate' as const)
        : ('/api/v1/admin/meeting-venues/{venue_id}/deactivate' as const);
      const result = await api.POST(path, { params: { path: { venue_id: venueId } } });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: AdminMeetingVenue }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: VENUES_KEY }),
  });
}
