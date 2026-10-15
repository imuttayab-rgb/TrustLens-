/** Client module; defines api. */

import { API_BASE_URL } from '@/config/environment';
import { createApiClient } from '@trustlens/api-client';
import { getAccessToken, refreshSession, setAccessToken } from '@/lib/auth/session';

export const api = createApiClient({
  baseUrl: API_BASE_URL,
  getAccessToken,
  onUnauthorized: async () => {
    const token = await refreshSession();
    setAccessToken(token);
    return token;
  },
});
