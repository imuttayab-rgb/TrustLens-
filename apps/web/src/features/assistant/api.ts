/** Api module; defines ChatReply, ListingResults, Listing, Filters, Source, Suggestions. */
import { api } from '@/lib/api/client';
import { unwrap, type ApiPaths } from '@trustlens/api-client';

type Data<
  Path extends keyof ApiPaths,
  Method extends keyof ApiPaths[Path],
> = ApiPaths[Path][Method] extends {
  responses: { 200: { content: { 'application/json': { data: infer T } } } };
}
  ? T
  : never;
export type ChatReply = Data<'/api/v1/assistant/chat', 'post'>;
export type ListingResults = Data<'/api/v1/assistant/listings', 'post'>;
export type Listing = ListingResults['items'][number];
export type Filters = ListingResults['filters'];
export type Source = ChatReply['sources'][number];
export type Suggestions = Data<'/api/v1/assistant/suggestions', 'get'>;
export type Description = Data<'/api/v1/assistant/description', 'post'>;
export type Research = Data<'/api/v1/assistant/research', 'post'>;
export type Status = Data<'/api/v1/assistant/status', 'get'>;
export type Enhancement = Data<'/api/v1/assistant/enhance', 'post'>;
type EnhanceInput =
  ApiPaths['/api/v1/assistant/enhance']['post']['requestBody']['content']['application/json'];

export class EnhancementError extends Error {
  constructor(
    message: string,
    readonly retryAfter = 0,
    readonly status = 0,
  ) {
    super(message);
    this.name = 'EnhancementError';
  }
}

export function retryAfterSeconds(value: string | null, now = Date.now()): number {
  const numeric = value === null ? 60 : Number(value);
  const seconds = Number.isFinite(numeric) ? numeric : (Date.parse(value ?? '') - now) / 1000;
  return Math.max(1, Math.min(86400, Number.isFinite(seconds) ? Math.ceil(seconds) : 60));
}
type ChatInput =
  ApiPaths['/api/v1/assistant/chat']['post']['requestBody']['content']['application/json'];
type DescriptionInput =
  ApiPaths['/api/v1/assistant/description']['post']['requestBody']['content']['application/json'];
type ResearchInput =
  ApiPaths['/api/v1/assistant/research']['post']['requestBody']['content']['application/json'];

export const assistantApi = {
  enhance: async (body: EnhanceInput, signal: AbortSignal) => {
    const result = await api.POST('/api/v1/assistant/enhance', { body, signal });
    if (result.response.status === 429) {
      throw new EnhancementError(
        'AI is busy. Your description and features are unchanged.',
        retryAfterSeconds(result.response.headers.get('Retry-After')),
        429,
      );
    }
    if (result.response.status === 401) {
      throw new EnhancementError(
        'Please sign in again. Your description and features are unchanged.',
        0,
        401,
      );
    }
    return unwrap<Enhancement>(result);
  },
  status: async () => unwrap<Status>(await api.GET('/api/v1/assistant/status')),
  chat: async (body: ChatInput, signal: AbortSignal) =>
    unwrap<ChatReply>(await api.POST('/api/v1/assistant/chat', { body, signal })),
  listings: async (body: Filters, signal?: AbortSignal) =>
    unwrap<ListingResults>(
      await api.POST('/api/v1/assistant/listings', { body, ...(signal ? { signal } : {}) }),
    ),
  suggestions: async (
    q: string,
    category: string | null,
    city: string | null,
    seller: boolean,
    signal: AbortSignal,
    offset = 0,
  ) =>
    unwrap<Suggestions>(
      await api.GET('/api/v1/assistant/suggestions', {
        signal,
        params: { query: { q, category, city, offset, mode: seller ? 'seller' : 'buyer' } },
      }),
    ),
  describe: async (body: DescriptionInput, signal: AbortSignal) =>
    unwrap<Description>(await api.POST('/api/v1/assistant/description', { body, signal })),
  research: async (body: ResearchInput, signal: AbortSignal) =>
    unwrap<Research>(await api.POST('/api/v1/assistant/research', { body, signal })),
};

export function askAssistant(message = '') {
  window.dispatchEvent(new CustomEvent('trustlens:ask', { detail: { message } }));
}
