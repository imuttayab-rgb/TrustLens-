/** Hooks module; defines Profile, ProfileAd, ProfileAds, useMyProfile, usePublicProfile, useProfileMutation. */
'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSession } from '@/lib/auth/use-session';
import { refreshSession, setAccessToken } from '@/lib/auth/session';
import type { RiskLevel } from '@trustlens/constants';
import { profileRequest } from './api';
export interface Profile {
  usernameLocked: boolean;
  initialized: boolean;
  userId: string;
  sellerId: string | null;
  handle: string;
  profileUrl: string;
  displayName: string;
  city: string | null;
  countryCode: string | null;
  bio: string | null;
  memberSince: string;
  nameVerified: boolean;
  photoMatched: boolean;
  photoUrl: string | null;
  canInteract: boolean;
  score: number | null;
  riskLevel: RiskLevel | null;
  verification: { identity: boolean; phone: boolean; email: boolean };
  email?: string;
  phone?: string | null;
  nameStatus?: string;
  legalName?: string | null;
  extractedName?: string | null;
  identityStatus?: string;
  photoStatus?: string;
  photoReason?: string | null;
  photoRequestId?: string | null;
  nameRequestStatus?: string | null;
  nameRequestNote?: string | null;
  version?: number;
}
export interface ProfileAd {
  id: string;
  title: string;
  price: number | null;
  currency: string | null;
  city: string | null;
  status: string;
  rawStatus: string;
  isPublic: boolean;
  imageUrl: string | null;
  createdAt: string;
}
export interface ProfileAds {
  items: ProfileAd[];
  total: number;
  counts: { all: number; active: number; inactive: number };
}
export function useMyProfile() {
  const { data: user } = useSession();
  return useQuery<Profile>({
    queryKey: ['profile', 'me', user?.id],
    enabled: Boolean(user),
    queryFn: async () => {
      let result = await profileRequest<Profile>('/me/profile');
      if (!result.initialized) {
        result = await profileRequest<Profile>('/me/profile/initialize', { method: 'POST' });
        const token = await refreshSession();
        if (token) setAccessToken(token);
      }
      return result;
    },
    staleTime: 10_000,
    refetchInterval: (query) =>
      ['QUEUED', 'PROCESSING'].includes(query.state.data?.photoStatus ?? '')
        ? 5000
        : query.state.data?.nameRequestStatus === 'REVIEW'
          ? 30_000
          : false,
    retry: 1,
  });
}
export function usePublicProfile(reference: string) {
  return useQuery<Profile>({
    queryKey: ['profile', 'public', reference],
    queryFn: () => profileRequest(`/public/profiles/${encodeURIComponent(reference)}`),
    retry: 1,
  });
}
export function useProfileMutation<T>(path: string, method = 'POST') {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: T) =>
      profileRequest<Profile>(path, { method, body: JSON.stringify(input) }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['profile'] });
      await qc.invalidateQueries({ queryKey: ['seller'] });
      await qc.invalidateQueries({ queryKey: ['listings'] });
    },
  });
}
export function useProfileAds(tab: string, q: string, offset: number) {
  return useQuery<ProfileAds>({
    queryKey: ['profile', 'ads', tab, q, offset],
    queryFn: () =>
      profileRequest(
        `/me/profile/ads?tab=${tab}&q=${encodeURIComponent(q)}&offset=${offset}&limit=12`,
      ),
    refetchInterval: 15_000,
  });
}
