/** Shared typed failures for generated and hand-written API requests. */
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
