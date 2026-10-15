/** Chatcasereview module; defines ChatCaseReview. */
'use client';
import { API_BASE_URL } from '@/config/environment';

import { useEffect, useState } from 'react';
import { getAccessToken, refreshSession, setAccessToken } from '@/lib/auth/session';
type Evidence = {
  id: string;
  senderId: string;
  kind: string;
  original: string;
  current: string | null;
  createdAt: string;
  deleted: boolean;
  hidden: boolean;
  versions: { body: string; at: string }[];
};
type CasePage = {
  conversationId: string;
  reason: string;
  messages: Evidence[];
  nextCursor: string | null;
};
async function request(path: string, init: RequestInit = {}) {
  const run = () =>
    fetch(`${API_BASE_URL}/api/v1/admin/chat-cases${path}`, {
      ...init,
      credentials: 'include',
      cache: 'no-store',
      headers: {
        Authorization: `Bearer ${getAccessToken() ?? ''}`,
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      },
    });
  let response = await run();
  if (response.status === 401) {
    setAccessToken(await refreshSession());
    response = await run();
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new Error(body?.error?.message ?? 'Could not open this case.');
  }
  return response;
}
export function ChatCaseReview({ reportId }: { reportId: string }) {
  const [page, setPage] = useState<CasePage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [audio, setAudio] = useState<string | null>(null);
  useEffect(
    () => () => {
      if (audio) URL.revokeObjectURL(audio);
    },
    [audio],
  );
  async function load(before?: string) {
    setBusy(true);
    setError(null);
    try {
      const response = await request(`/${reportId}${before ? `?before=${before}` : ''}`);
      const body = (await response.json()) as { data: CasePage };
      setPage((old) =>
        before && old
          ? { ...body.data, messages: [...body.data.messages, ...old.messages] }
          : body.data,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Review failed.');
    } finally {
      setBusy(false);
    }
  }
  async function hide(messageId: string) {
    setBusy(true);
    setError(null);
    try {
      await request(`/${reportId}/hide`, {
        method: 'POST',
        body: JSON.stringify({ messageId, reason }),
      });
      setPage((old) =>
        old
          ? {
              ...old,
              messages: old.messages.map((m) => (m.id === messageId ? { ...m, hidden: true } : m)),
            }
          : old,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not hide.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="rounded border border-border p-3 text-sm">
      {!page ? (
        <button disabled={busy} onClick={() => void load()} className="underline">
          {busy ? 'Loading…' : 'Review retained chat evidence'}
        </button>
      ) : (
        <>
          <p className="font-semibold">Chat case · {page.reason.replaceAll('_', ' ')}</p>
          <p className="my-2 text-xs text-muted-foreground">
            Every review and audio access is audited. Original records stay retained when hidden
            from users.
          </p>
          <label className="block text-xs">
            Reason required before hiding a message
            <input
              value={reason}
              maxLength={1000}
              onChange={(e) => setReason(e.target.value)}
              className="my-2 w-full rounded border border-input bg-background p-2"
              placeholder="Explain why user visibility should be removed"
            />
          </label>
          {page.nextCursor && (
            <button
              disabled={busy}
              onClick={() => void load(page.nextCursor as string)}
              className="my-2 underline"
            >
              Load earlier evidence
            </button>
          )}
          <div className="max-h-96 space-y-3 overflow-y-auto">
            {page.messages.map((m) => (
              <div key={m.id} className="rounded bg-muted/40 p-3">
                <p className="text-[11px] text-muted-foreground">
                  {m.senderId} · {new Date(m.createdAt).toLocaleString()}
                  {m.deleted ? ' · User deleted' : ''}
                  {m.hidden ? ' · Hidden by support' : ''}
                </p>
                <p className="mt-1 whitespace-pre-wrap break-words">Original: {m.original}</p>
                {m.current !== null && (
                  <p className="mt-1 whitespace-pre-wrap break-words">Latest edit: {m.current}</p>
                )}
                {m.versions.length > 0 && (
                  <details>
                    <summary className="cursor-pointer text-xs">
                      Edit history ({m.versions.length})
                    </summary>
                    {m.versions.map((v, i) => (
                      <p key={i} className="mt-1 whitespace-pre-wrap break-words text-xs">
                        {new Date(v.at).toLocaleString()} · {v.body}
                      </p>
                    ))}
                  </details>
                )}
                {m.kind === 'voice' && (
                  <button
                    disabled={busy}
                    className="mr-3 mt-2 text-xs underline"
                    onClick={() => {
                      setError(null);
                      void request(`/${reportId}/audio/${m.id}`)
                        .then((r) => r.blob())
                        .then((blob) => setAudio(URL.createObjectURL(blob)))
                        .catch((e) =>
                          setError(e instanceof Error ? e.message : 'Audio unavailable.'),
                        );
                    }}
                  >
                    Play retained voice
                  </button>
                )}
                {!m.hidden && (
                  <button
                    disabled={busy || reason.trim().length < 10}
                    onClick={() => void hide(m.id)}
                    className="mt-2 text-xs text-destructive underline"
                  >
                    Hide from both users
                  </button>
                )}
              </div>
            ))}
          </div>
          {/* Private user recording; no transcript is available. */}
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          {audio && <audio key={audio} controls autoPlay src={audio} className="mt-3 w-full" />}
        </>
      )}
      {error && (
        <p role="alert" className="mt-2 text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
