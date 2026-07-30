import { cookies } from 'next/headers';

/**
 * Admin server fetcher.
 *
 * Every admin read is `no-store`: a reviewer looking at a queue must never see
 * a cached page, and a stale identity decision is worse than a slow one.
 */
export async function adminFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  const base = process.env.API_BASE_URL_INTERNAL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
  const cookieHeader = (await cookies()).toString();

  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(cookieHeader ? { Cookie: cookieHeader } : {}),
      ...init?.headers,
    },
    cache: 'no-store',
  });

  if (!response.ok) return null;
  const body = (await response.json()) as { data: T };
  return body.data;
}
