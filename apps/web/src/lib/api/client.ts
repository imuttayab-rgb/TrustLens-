import { createApiClient } from '@trustlens/api-client';
import { getAccessToken, refreshSession, setAccessToken } from '@/lib/auth/session';

/**
 * Browser-side API client.
 *
 * The access token lives in memory only - never localStorage - so an XSS
 * payload cannot read it. The refresh token is an httpOnly cookie the client
 * never touches (ADR-0006).
 */
export const api = createApiClient({
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000',
  getAccessToken,
  onUnauthorized: async () => {
    const token = await refreshSession();
    setAccessToken(token);
    return token;
  },
});
