/** Shared bounded JSON transport. Keeps credentials, refresh, parsing and errors consistent. */
import { ApiError } from './errors';
export interface JsonRequesterOptions {
  baseUrl: string;
  getAccessToken: () => string | null;
  onUnauthorized: () => Promise<string | null>;
  timeoutMs?: number;
}
/** Create one app-local requester; token state is never shared between web and admin. */
export function createJsonRequester(options: JsonRequesterOptions) {
  return async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    if (!path.startsWith('/') || path.startsWith('//'))
      throw new Error('API paths must be relative to /api/v1.');
    const controller = new AbortController();
    const abort = () => controller.abort(init.signal?.reason);
    if (init.signal?.aborted) abort();
    else init.signal?.addEventListener('abort', abort, { once: true });
    const timer = setTimeout(
      () => controller.abort(new DOMException('Request timed out', 'TimeoutError')),
      options.timeoutMs ?? 15000,
    );
    async function send() {
      const headers = new Headers(init.headers);
      headers.set('Accept', 'application/json');
      const token = options.getAccessToken();
      if (token) headers.set('Authorization', `Bearer ${token}`);
      if (typeof init.body === 'string' && !headers.has('Content-Type'))
        headers.set('Content-Type', 'application/json');
      return fetch(`${options.baseUrl}/api/v1${path}`, {
        ...init,
        headers,
        signal: controller.signal,
        credentials: 'include',
        cache: 'no-store',
      });
    }
    try {
      let response = await send();
      if (response.status === 401 && !path.startsWith('/auth/')) {
        if (await options.onUnauthorized()) response = await send();
      }
      if (response.status === 204 && response.ok) return undefined as T;
      const body: unknown = await response.json().catch(() => null);
      const object = body && typeof body === 'object' ? (body as Record<string, unknown>) : null;
      if (!response.ok) {
        const requestId = typeof object?.requestId === 'string' ? object.requestId : undefined;
        const detail =
          response.status >= 500
            ? 'The service is temporarily unavailable. Please try again.'
            : typeof object?.detail === 'string'
              ? object.detail
              : `Request failed (${response.status}). Please try again.`;
        throw new ApiError({
          type: 'about:blank',
          title: 'Request failed',
          status: response.status,
          detail,
          code: typeof object?.code === 'string' ? object.code : `HTTP_${response.status}`,
          ...(requestId ? { requestId } : {}),
          ...(response.status < 500 && Array.isArray(object?.errors)
            ? {
                errors: object.errors.filter(
                  (item): item is { field: string; code: string; message: string } =>
                    !!item &&
                    typeof item === 'object' &&
                    typeof item.field === 'string' &&
                    typeof item.code === 'string' &&
                    typeof item.message === 'string',
                ),
              }
            : {}),
        });
      }
      if (!object || !('data' in object))
        throw new ApiError({
          type: 'about:blank',
          title: 'Invalid response',
          status: response.status,
          detail: 'The server returned an invalid response. Please try again.',
          code: 'INVALID_RESPONSE',
        });
      return object.data as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (init.signal?.aborted) throw error;
      throw new ApiError({
        type: 'about:blank',
        title: 'Connection problem',
        status: 0,
        detail: controller.signal.aborted
          ? 'The request timed out. Please try again.'
          : 'Cannot reach the server. Check your connection and try again.',
        code: controller.signal.aborted ? 'REQUEST_TIMEOUT' : 'NETWORK_ERROR',
      });
    } finally {
      clearTimeout(timer);
      init.signal?.removeEventListener('abort', abort);
    }
  };
}
