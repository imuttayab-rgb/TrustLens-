/**
 * One key factory for the whole app.
 *
 * Centralised because invalidation bugs come from two call sites building the
 * "same" key slightly differently.
 */
export const qk = {
  me: ['me'] as const,
  seller: {
    me: ['seller', 'me'] as const,
    byHandle: (handle: string) => ['seller', 'handle', handle] as const,
  },
  trustScore: {
    current: (sellerId: string) => ['trust-score', sellerId, 'current'] as const,
    history: (sellerId: string) => ['trust-score', sellerId, 'history'] as const,
    improvements: (sellerId: string) => ['trust-score', sellerId, 'improvements'] as const,
  },
  listing: {
    all: ['listings'] as const,
    list: (limit: number, offset: number) => ['listings', 'list', limit, offset] as const,
    byId: (id: string) => ['listings', id] as const,
  },
  verification: { status: ['verification', 'status'] as const },
  job: { status: (jobId: string) => ['job', jobId] as const },
  appeal: { mine: ['appeals', 'mine'] as const },
} as const;
