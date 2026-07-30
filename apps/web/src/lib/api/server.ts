import { cookies } from 'next/headers';

/**
 * Server-component fetcher.
 *
 * Uses the internal API URL (container network in production) and forwards
 * cookies, so a server render is authenticated exactly like the browser would
 * be. Never imported into a client component - it would leak the internal URL
 * into the browser bundle.
 */
export async function serverFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  const base = process.env.API_BASE_URL_INTERNAL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
  const cookieHeader = (await cookies()).toString();

  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(cookieHeader ? { Cookie: cookieHeader } : {}),
      ...init?.headers,
    },
    // The public seller page is cached; the TTL mirrors the API's own score
    // cache so the two cannot disagree by more than one window.
    next: { revalidate: 300, ...init?.next },
  });

  if (!response.ok) return null;
  const body = (await response.json()) as { data: T };
  return body.data;
}
