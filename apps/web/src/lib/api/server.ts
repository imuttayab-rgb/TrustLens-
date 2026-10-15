/** Server module; defines ApiUnavailableError, serverFetch. */
import { cookies } from 'next/headers';
export class ApiUnavailableError extends Error {
  constructor(readonly status: number) {
    super('The service could not load this page. Please try again.');
    this.name = 'ApiUnavailableError';
  }
}
export async function serverFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  const base = process.env.API_BASE_URL_INTERNAL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) throw new ApiUnavailableError(503);
  const cookieHeader = (await cookies()).toString();
  const headers = new Headers(init?.headers);
  headers.set('Accept', 'application/json');
  if (cookieHeader) headers.set('Cookie', cookieHeader);
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      headers,
      cache: 'no-store',
      next: { revalidate: 0 },
      signal: init?.signal ?? AbortSignal.timeout(15000),
    });
  } catch {
    throw new ApiUnavailableError(503);
  }
  if (response.status === 404) return null;
  if (!response.ok) throw new ApiUnavailableError(response.status);
  try {
    const body = (await response.json()) as { data?: T };
    if (!body || !('data' in body)) throw new ApiUnavailableError(502);
    return body.data ?? null;
  } catch {
    throw new ApiUnavailableError(502);
  }
}
