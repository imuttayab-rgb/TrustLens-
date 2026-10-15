import { API_BASE_URL } from '@/config/environment';
import { createApiClient } from '@trustlens/api-client';
import { getAccessToken, refreshSession, setAccessToken } from '@/lib/auth/session';

/**
 * Browser-side API client.
 *
 * The access token lives in memory only - never localStorage - so it is not persisted across browser restarts. XSS defenses remain necessary. The refresh token is an httpOnly cookie the client
 * never touches (ADR-0006).
 */
export const api = createApiClient({
  baseUrl: API_BASE_URL,
  getAccessToken,
  onUnauthorized: async () => {
    const token = await refreshSession();
    setAccessToken(token);
    return token;
  },
});
