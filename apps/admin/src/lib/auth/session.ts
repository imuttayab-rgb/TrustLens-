'use client';
import { API_BASE_URL } from '@/config/environment';

/**
 * In-memory session store.
 *
 * Deliberately a module-level variable rather than storage: the token dies
 * with the tab, and it is not persisted in browser storage. In-memory tokens still require XSS defenses. That matters more here than
 * on the seller app - this token can read identity documents.
 */
let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

/** Exchange the httpOnly refresh cookie for a new access token. */
let refreshInFlight: Promise<string | null> | null = null;
export function refreshSession(): Promise<string | null> {
  if (!refreshInFlight)
    refreshInFlight = refreshOnce().finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}
async function refreshOnce(): Promise<string | null> {
  const base = API_BASE_URL;
  try {
    const response = await fetch(`${base}/api/v1/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) return null;
    const body = (await response.json()) as { data: { accessToken: string } };
    return body.data.accessToken;
  } catch {
    return null;
  }
}
