'use client';

import { api } from '@/lib/api/client';
import { setAccessToken } from '@/lib/auth/session';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import { useRouter } from 'next/navigation';

/**
 * Signs out of the current staff session.
 *
 * Clears local state and redirects even if the network call fails (an
 * already-expired refresh cookie is not a reason to strand someone on a
 * page that now 401s on every request).
 */
export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: async () => {
      const result = await api.POST('/api/v1/auth/logout');
      if (result.error) throw toApiError(result.error);
    },
    onSettled: () => {
      setAccessToken(null);
      queryClient.setQueryData(['me'], null);
      queryClient.clear();
      router.push('/login');
    },
  });
}
