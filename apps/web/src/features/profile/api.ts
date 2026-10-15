'use client';
/** App binding for the shared authenticated JSON transport. */
import { API_BASE_URL } from '@/config/environment';
import { getAccessToken, refreshSession, setAccessToken } from '@/lib/auth/session';
import { createJsonRequester } from '@trustlens/api-client';
export const apiBase = API_BASE_URL;
export const photoUrl = (path: string | null | undefined) => (path ? `${apiBase}${path}` : null);
export const profileRequest = createJsonRequester({
  baseUrl: apiBase,
  getAccessToken,
  onUnauthorized: async () => {
    const token = await refreshSession();
    setAccessToken(token);
    return token;
  },
});
