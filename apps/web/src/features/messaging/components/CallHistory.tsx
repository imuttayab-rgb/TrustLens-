'use client';
/** On-demand, participant-scoped call history; queries stop when collapsed. */
import { profileRequest } from '@/features/profile';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { reasonLabel } from '../calls/labels';
import type { Call } from '../calls/types';
import { voiceTime } from './VoicePlayback';
export function CallHistory({ conversationId }: { conversationId: string }) {
  const [open, setOpen] = useState(false);
  const history = useQuery({
    queryKey: ['call-history', conversationId],
    queryFn: () => profileRequest<Call[]>(`/me/conversations/${conversationId}/calls`),
    enabled: open,
    refetchInterval: open ? 5000 : false,
  });
  return (
    <div className="border-b border-border px-3 py-2 text-xs">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="underline">
        {open ? 'Hide call history' : 'Call history'}
      </button>
      {open && (
        <div className="mt-2 max-h-40 space-y-2 overflow-auto" aria-label="Call history">
          {history.isError ? (
            <p>Could not load call history. Please try again.</p>
          ) : history.isPending ? (
            <p>Loading…</p>
          ) : !history.data?.length ? (
            <p>No calls in your current chat history.</p>
          ) : (
            history.data.map((row) => (
              <div key={row.id} className="flex justify-between gap-3">
                <span>
                  {row.direction === 'outgoing' ? 'Outgoing' : 'Incoming'} ·{' '}
                  {row.state === 'ended'
                    ? (reasonLabel[row.reason ?? 'ended'] ?? 'Call ended')
                    : row.state}
                  {row.connectedAt && row.endedAt
                    ? ` · ${voiceTime(Math.max(0, (Date.parse(row.endedAt) - Date.parse(row.connectedAt)) / 1000))}`
                    : ''}
                </span>
                <time>{new Date(row.createdAt).toLocaleString()}</time>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
