/** Use logout module; defines useLogout. */
'use client';

import { clearDraftRecovery } from '@/lib/draft-recovery-cache';
import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { setAccessToken } from '@/lib/auth/session';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import { useRouter } from 'next/navigation';

/**
 * Signs out of the *current* session - distinct from Settings' "Sign out"
 * per listed device, which revokes a session other than this one.
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
      window.dispatchEvent(new Event('tl:logout'));
      clearDraftRecovery();
      setAccessToken(null);
      queryClient.setQueryData(qk.me, null);
      queryClient.clear();
      router.push('/login');
    },
  });
}
