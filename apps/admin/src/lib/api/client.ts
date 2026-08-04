import { createApiClient } from '@trustlens/api-client';
import { getAccessToken, refreshSession, setAccessToken } from '@/lib/auth/session';

export const api = createApiClient({
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000',
  getAccessToken,
  onUnauthorized: async () => {
    const token = await refreshSession();
    setAccessToken(token);
    return token;
  },
});
