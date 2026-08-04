'use client';

/**
 * In-memory session store.
 *
 * Deliberately a module-level variable rather than storage: the token dies
 * with the tab, and no XSS payload can read it. That matters more here than
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
export async function refreshSession(): Promise<string | null> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
  try {
    const response = await fetch(`${base}/api/v1/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!response.ok) return null;
    const body = (await response.json()) as { data: { accessToken: string } };
    return body.data.accessToken;
  } catch {
    return null;
  }
}
