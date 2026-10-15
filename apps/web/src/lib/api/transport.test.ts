/** Contract checks for both apps' shared request/error boundary. No real network. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createJsonRequester } from '@trustlens/api-client';

const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
const make = (overrides = {}) =>
  createJsonRequester({
    baseUrl: 'https://api.example.test',
    getAccessToken: () => 'current-token',
    onUnauthorized: () => Promise.resolve(null),
    ...overrides,
  });
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
describe('JSON transport', () => {
  it('preserves credentials, headers and data', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(response({ data: { id: 1 } }));
    vi.stubGlobal('fetch', fetch);
    expect(await make()('/me', { method: 'POST', body: '{}' })).toEqual({ id: 1 });
    const [url, init] = fetch.mock.calls[0]!;
    expect(url).toBe('https://api.example.test/api/v1/me');
    expect(init?.credentials).toBe('include');
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer current-token');
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json');
  });
  it('retries once after session refresh and does not refresh auth routes', async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(response({}, 401))
      .mockResolvedValueOnce(response({ data: 'ok' }));
    const refresh = vi.fn<() => Promise<string | null>>().mockResolvedValue('new');
    vi.stubGlobal('fetch', fetch);
    expect(await make({ onUnauthorized: refresh })('/me')).toBe('ok');
    expect(refresh).toHaveBeenCalledTimes(1);
    fetch.mockResolvedValue(response({}, 401));
    await expect(make({ onUnauthorized: refresh })('/auth/login')).rejects.toMatchObject({
      status: 401,
    });
    expect(refresh).toHaveBeenCalledTimes(1);
  });
  it('rejects malformed success bodies and accepts 204', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn<typeof globalThis.fetch>()
        .mockResolvedValueOnce(new Response('<html>oops</html>'))
        .mockResolvedValueOnce(new Response(null, { status: 204 })),
    );
    await expect(make()('/me')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
    expect(await make()('/me', { method: 'DELETE' })).toBeUndefined();
  });
  it('keeps validation context while ignoring malformed field errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof globalThis.fetch>().mockResolvedValue(
        response(
          {
            detail: 'Invalid name',
            requestId: 'req-1',
            code: 'VALIDATION_ERROR',
            errors: [null, {}, { field: 'name', code: 'required', message: 'Required' }],
          },
          422,
        ),
      ),
    );
    await expect(make()('/me')).rejects.toMatchObject({
      code: 'VALIDATION_ERROR',
      requestId: 'req-1',
      fieldErrors: { name: 'Required' },
    });
  });
  it('does not expose raw server error details', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof globalThis.fetch>().mockResolvedValue(
        response(
          {
            detail: 'private SQL traceback',
            errors: [{ field: 'sql', code: 'db', message: 'secret' }],
          },
          500,
        ),
      ),
    );
    await expect(make()('/me')).rejects.toMatchObject({
      status: 500,
      message: 'The service is temporarily unavailable. Please try again.',
      fieldErrors: {},
    });
  });
  it('bounds stalled network requests and distinguishes caller cancellation', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof globalThis.fetch>(
        (_url, init) =>
          new Promise<Response>((_resolve, reject) => {
            const signal = init?.signal;
            signal?.addEventListener(
              'abort',
              () => {
                const reason: unknown = signal.reason;
                reject(reason instanceof Error ? reason : new Error('Aborted'));
              },
              { once: true },
            );
          }),
      ),
    );
    const timeout = expect(make({ timeoutMs: 10 })('/me')).rejects.toMatchObject({
      code: 'REQUEST_TIMEOUT',
    });
    await vi.advanceTimersByTimeAsync(11);
    await timeout;
    const controller = new AbortController();
    const reason = new DOMException('Cancelled', 'AbortError');
    const cancelled = expect(make()('/me', { signal: controller.signal })).rejects.toBe(reason);
    controller.abort(reason);
    await cancelled;
  });
  it('rejects absolute URLs before sending credentials', async () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    await expect(make()('//evil.example.test')).rejects.toThrow('relative');
    expect(fetch).not.toHaveBeenCalled();
  });
});
