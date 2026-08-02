'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';

/**
 * Submits a device fingerprint once per page session.
 *
 * Headless on purpose: it renders nothing and never blocks. A seller should
 * not be made to wait on, or even notice, a signal that only ever *lowers* a
 * score when the same device is behind several accounts.
 *
 * ThumbmarkJS (MIT) rather than FingerprintJS v4, which is BSL-licensed and
 * restricted in production.
 *
 * Only the hash and four coarse attributes go up, because that is all
 * `DeviceFingerprintRequest` accepts today. That is a known limitation, not a
 * design choice: a hash alone is brittle, since one browser update shifts a
 * component, changes the whole hash, and orphans the device history. Storing
 * the component vector so the backend can match by similarity needs an API
 * field first - tracked as P2-19.
 *
 * Either way the signal stays evidence, never proof of identity:
 * open-source fingerprinting is only 60-80% accurate, so it may lower a score
 * when several accounts share a device but must never confirm who someone is.
 */
export function DeviceCheck() {
  const queryClient = useQueryClient();
  const submitted = useRef(false);

  useEffect(() => {
    if (submitted.current) return;
    submitted.current = true;

    void (async () => {
      try {
        // Imported lazily so the fingerprinting bundle never lands in the
        // critical path of a page that only reads a score.
        const { getFingerprint } = await import('@thumbmarkjs/thumbmarkjs');
        const fingerprint = await getFingerprint();

        const result = await api.POST('/api/v1/verification/device', {
          body: {
            fingerprint,
            userAgent: navigator.userAgent,
            screenResolution: `${window.screen.width}x${window.screen.height}`,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            languages: navigator.languages.join(','),
          },
        });

        if (!result.error) {
          await queryClient.invalidateQueries({ queryKey: qk.verification.status });
        }
      } catch {
        // Never surface this. A blocked fingerprinting API or an offline tab
        // must not produce an error a seller cannot act on; the signal simply
        // resolves as UNAVAILABLE and costs them nothing.
      }
    })();
  }, [queryClient]);

  return null;
}
