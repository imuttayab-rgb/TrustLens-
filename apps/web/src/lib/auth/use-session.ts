/** Use session module; defines SessionUser, useSession. */
'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { useQuery } from '@tanstack/react-query';

export interface SessionUser {
  id: string;
  email: string;
  fullName: string;
  status: string;
  roles: string[];
  permissions: string[];
}

/**
 * Establish the signed-in user on the client.
 *
 * Signed-in pages cannot be server-rendered in this design, and the reason is
 * structural rather than a preference:
 *
 * The API accepts an access token only from the `Authorization` header, and
 * the sole cookie - `tl_rt` - is httpOnly and path-scoped to `/api/v1/auth`,
 * so it is not even transmitted to `/api/v1/me`. A React server component has
 * no access to the in-memory access token and cannot mint one either, because
 * `/auth/refresh` rotates the refresh token and a server component may not
 * set the replacement cookie. Any server render of an authenticated page is
 * therefore guaranteed to look signed out.
 *
 * Fetching on the client is not a workaround but the correct half of the
 * split: authenticated pages are private and gain nothing from SSR, while the
 * public seller page - the one that needs to be fast and indexable - reads the
 * public API and stays server-rendered.
 *
 * On a hard navigation the in-memory token is empty, so the first call 401s,
 * the client middleware exchanges the refresh cookie for a new access token
 * and retries. That path is already built; this hook just primes it.
 *
 * Deliberately does NOT pre-emptively call `refreshSession()` itself: doing
 * that here as well as in the api-client's `onUnauthorized` middleware gave
 * a hard navigation two independent, un-deduplicated refresh calls (this
 * hook's, and whichever other authenticated query 401ed first) racing the
 * same rotating refresh cookie - the loser got a 401 the server correctly
 * treats as token reuse and revokes the whole session, signing the user back
 * out. Always going through the single request below routes every refresh
 * through the client's one deduped `refreshing` promise instead.
 */
export function useSession() {
  return useQuery<SessionUser | null>({
    queryKey: qk.me,
    queryFn: async () => {
      const result = await api.GET('/api/v1/me');
      if (result.error) return null;
      return (result.data as { data: SessionUser }).data;
    },
    // A failure here means "not signed in", which is an answer, not an error
    // worth retrying.
    retry: false,
    staleTime: 5 * 60_000,
  });
}
