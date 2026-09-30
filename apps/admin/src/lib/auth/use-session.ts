'use client';

import { api } from '@/lib/api/client';
import { useQuery } from '@tanstack/react-query';

export interface AdminUser {
  id: string;
  email: string;
  fullName: string;
  roles: string[];
  permissions: string[];
}

/** Roles allowed anywhere in this app. */
export const STAFF_ROLES = ['ADMIN', 'REVIEWER'] as const;

/**
 * Establish the signed-in staff user.
 *
 * Client-side for the same structural reason as the seller app: the API reads
 * the access token only from the Authorization header, and the refresh cookie
 * is path-scoped to /api/v1/auth, so a server component can never authenticate
 * (see P0-14). The first call 401s on a cold load, the client middleware
 * exchanges the cookie, and it retries.
 *
 * Deliberately does not pre-emptively refresh itself - see the web app's
 * `useSession` for why: a second, un-deduplicated refresh call here would
 * race the api-client's own deduped one over the same rotating refresh
 * cookie and can get the whole session revoked as token reuse.
 */
export function useSession() {
  return useQuery<AdminUser | null>({
    queryKey: ['me'],
    queryFn: async () => {
      const result = await api.GET('/api/v1/me');
      if (result.error) return null;
      return (result.data as { data: AdminUser }).data;
    },
    retry: false,
    staleTime: 5 * 60_000,
  });
}
