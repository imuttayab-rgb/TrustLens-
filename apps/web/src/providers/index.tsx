/** Index module; defines Providers. */
'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { VoicePlaybackProvider } from '@/features/messaging';
import { VoiceCallProvider } from '@/features/messaging';

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Scores change rarely; refetching on every focus is wasted work.
            staleTime: 60_000,
            retry: (failureCount, error) => {
              // Never retry an auth or validation failure - the answer will
              // not change, and retrying a 401 races the refresh flow.
              const status = (error as { status?: number })?.status ?? 0;
              if (status === 401 || status === 403 || status === 422) return false;
              return failureCount < 2;
            },
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <VoicePlaybackProvider>
        <VoiceCallProvider>{children}</VoiceCallProvider>
      </VoicePlaybackProvider>
    </QueryClientProvider>
  );
}
