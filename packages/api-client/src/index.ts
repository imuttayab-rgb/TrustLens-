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

/** RFC 9457 problem+json, as produced by the API's exception handlers. */
export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail: string;
  code: string;
  instance?: string;
  requestId?: string;
  errors?: { field: string; code: string; message: string }[];
}

/**
 * A normalised API failure.
 *
 * `code` is the stable machine string to switch on. `requestId` is surfaced
 * in the UI so a user can quote it - which turns a 30-minute log hunt into a
 * single query.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly title: string;
  // `| undefined` rather than `?:` - the tsconfig sets
  // exactOptionalPropertyTypes, under which an optional property may be
  // absent but may not be *assigned* undefined. It is always assigned here.
  readonly requestId: string | undefined;
  readonly fieldErrors: Record<string, string>;

  constructor(problem: ProblemDetail) {
    super(problem.detail || problem.title);
    this.name = 'ApiError';
    this.status = problem.status;
    this.code = problem.code;
    this.title = problem.title;
    this.requestId = problem.requestId;
    this.fieldErrors = Object.fromEntries((problem.errors ?? []).map((e) => [e.field, e.message]));
  }

  get isAuthError(): boolean {
    return this.status === 401;
  }

  get isValidationError(): boolean {
    return this.status === 422;
  }
}

export interface ClientOptions {
  baseUrl: string;
  /** Returns the in-memory access token. Never read from storage (ADR-0006). */
  getAccessToken?: () => string | null;
  /** Called once on 401 so the caller can rotate and retry. */
  onUnauthorized?: () => Promise<string | null>;
}

export function createApiClient(options: ClientOptions) {
  const client = createClient<ApiPaths>({
    baseUrl: options.baseUrl,
    // Required so the httpOnly refresh cookie is sent to /auth endpoints.
    credentials: 'include',
  });

  let refreshing: Promise<string | null> | null = null;

  const auth: Middleware = {
    async onRequest({ request }) {
      const token = options.getAccessToken?.();
      if (token) request.headers.set('Authorization', `Bearer ${token}`);
      request.headers.set('Accept', 'application/json');
      return request;
    },

    async onResponse({ request, response }) {
      if (response.status !== 401 || !options.onUnauthorized) return response;
      // Never retry the refresh call itself - that is an infinite loop.
      if (request.url.includes('/auth/refresh')) return response;

      // Collapse concurrent 401s into ONE refresh. Without this, five parallel
      // requests each rotate the token and four of them present a token the
      // fifth has already superseded - which the server correctly treats as
      // reuse and revokes the whole session.
      refreshing ??= options.onUnauthorized().finally(() => {
        refreshing = null;
      });
      const token = await refreshing;
      if (!token) return response;

      const retried = request.clone();
      retried.headers.set('Authorization', `Bearer ${token}`);
      return fetch(retried);
    },
  };

  client.use(auth);
  return client;
}

/** Turn any thrown value into a usable `ApiError`. */
export function toApiError(error: unknown, fallbackMessage = 'Something went wrong.'): ApiError {
  if (error instanceof ApiError) return error;

  if (error && typeof error === 'object' && 'code' in error && 'status' in error) {
    return new ApiError(error as ProblemDetail);
  }

  return new ApiError({
    type: 'about:blank',
    title: 'Request failed',
    status: 0,
    detail: error instanceof Error ? error.message : fallbackMessage,
    code: 'NETWORK_ERROR',
  });
}

/** Unwrap the `{data, meta}` envelope, raising a typed error on failure. */
export function unwrap<T>(result: { data?: { data: T }; error?: unknown }): T {
  if (result.error) throw toApiError(result.error);
  if (!result.data) throw toApiError(null, 'Empty response from the server.');
  return result.data.data;
}
