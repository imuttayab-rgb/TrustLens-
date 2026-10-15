/**
 * Typed API client.
 *
 * `schema.gen.ts` is GENERATED from the backend's OpenAPI document
 * (`pnpm codegen`) and must never be hand-edited. CI regenerates it and fails
 * on drift, so a backend field rename breaks the frontend type-check in the
 * same PR - which is exactly where it should break (ADR-0005).
 */
import createClient, { type Middleware } from 'openapi-fetch';
import type { paths } from './schema.gen';

/** Every route the backend exposes, generated from its OpenAPI document. */
export type ApiPaths = paths;

import { toApiError } from './errors';
export { ApiError, toApiError, type ProblemDetail } from './errors';
export { createJsonRequester } from './transport';

export interface ClientOptions {
  baseUrl: string;
  /** Returns the in-memory access token. Never read from storage (ADR-0006). */
  getAccessToken?: () => string | null;
  /** Called once on 401 so the caller can rotate and retry. */
  onUnauthorized?: () => Promise<string | null>;
}

/**
 * Endpoints where a 401 is a normal business response about the credential
 * or token *in the request itself* (wrong password, wrong MFA code, an
 * expired reset/verification link) rather than a sign that the caller's
 * access token needs refreshing - these calls only ever run signed out, so
 * there was never a session token to expire in the first place.
 */
const CREDENTIAL_ENDPOINTS = [
  '/auth/login',
  '/auth/register',
  '/auth/refresh',
  '/auth/mfa/verify',
  '/auth/forgot-password',
  '/auth/reset-password',
];

export function createApiClient(options: ClientOptions) {
  const client = createClient<ApiPaths>({
    baseUrl: options.baseUrl,
    // Required so the httpOnly refresh cookie is sent to /auth endpoints.
    credentials: 'include',
  });

  let refreshing: Promise<string | null> | null = null;

  // A `Request` can only be `.clone()`d before its body stream is read - and
  // `fetch(request)` reads it. By the time `onResponse` sees a 401, the
  // request that produced it has already been sent, so cloning it there
  // throws "body is already used" for any POST/PUT/PATCH (the failure the
  // login form hit). Cloning eagerly in `onRequest`, before the request is
  // ever sent, keeps a fresh, unread copy ready for the retry below.
  const retryBodies = new Map<string, Request>();

  const auth: Middleware = {
    async onRequest({ request, id }) {
      const token = options.getAccessToken?.();
      if (token) request.headers.set('Authorization', `Bearer ${token}`);
      request.headers.set('Accept', 'application/json');
      retryBodies.set(id, request.clone());
      return request;
    },

    async onResponse({ request, response, id }) {
      const stashedRequest = retryBodies.get(id);
      retryBodies.delete(id);

      if (response.status !== 401 || !options.onUnauthorized) return response;
      // These endpoints establish or replace credentials rather than using
      // an existing session, so their 401 means "wrong password" / "wrong
      // code" / "expired reset link" - never "the access token expired".
      // Retrying them after a refresh would replay the same rejected
      // credentials and, if a refresh cookie from some other session
      // happens to be sitting in the browser, could quietly sign the form
      // in as someone else instead of surfacing the real rejection.
      // Every other 401 (including a hard navigation's very first call,
      // which never had a token to attach in the first place) is treated
      // as "the session needs refreshing", matching how this client has
      // always worked.
      const isCredentialEndpoint = CREDENTIAL_ENDPOINTS.some((path) => request.url.includes(path));
      if (isCredentialEndpoint) return response;

      // Collapse concurrent 401s into ONE refresh. Without this, five parallel
      // requests each rotate the token and four of them present a token the
      // fifth has already superseded - which the server correctly treats as
      // reuse and revokes the whole session.
      refreshing ??= options.onUnauthorized().finally(() => {
        refreshing = null;
      });
      const token = await refreshing;
      if (!token || !stashedRequest) return response;

      const retried = stashedRequest;
      retried.headers.set('Authorization', `Bearer ${token}`);
      return fetch(retried);
    },

    async onError({ id }) {
      retryBodies.delete(id);
    },
  };

  client.use(auth);
  return client;
}

/** Unwrap the `{data, meta}` envelope, raising a typed error on failure. */
export function unwrap<T>(result: { data?: { data: T }; error?: unknown }): T {
  if (result.error) throw toApiError(result.error);
  if (!result.data) throw toApiError(null, 'Empty response from the server.');
  return result.data.data;
}
