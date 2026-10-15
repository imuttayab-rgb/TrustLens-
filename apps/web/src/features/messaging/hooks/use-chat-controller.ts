/** Chat mutations, deadlines, draft state and pagination ownership.
 * Server records use React Query; drafts are scoped to the mounted conversation.
 */
'use client';
import { profileRequest } from '@/features/profile';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useVoiceCalls } from '../components/VoiceCalls';
import { useVoicePlayer } from '../components/VoicePlayback';
import {
  useMessages,
  useSendMessage,
  type ConversationSummary,
  type Message,
} from '../hooks/use-messaging';

export type ChatOptions = {
  conversation: ConversationSummary;
  userId: string;
  profileReady: boolean;
};
export function useChatController({ conversation, profileReady }: ChatOptions) {
  const query = useMessages(conversation.id);
  const messages = useMemo(() => query.data ?? [], [query.data]);
  const lastMessageId = messages.at(-1)?.id;
  const send = useSendMessage();
  const client = useQueryClient();
  const player = useVoicePlayer();
  const calls = useVoiceCalls();
  const [draft, setDraft] = useState('');
  const [reply, setReply] = useState<Message | null>(null);
  const [editing, setEditing] = useState<Message | null>(null);
  const [editBody, setEditBody] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());
  const clock = useRef({ server: Date.now(), at: performance.now() });
  const [undo, setUndo] = useState<{ undoToken: string; undoUntil: string } | null>(null);
  const [recording, setRecording] = useState(false);
  const [report, setReport] = useState<Message | 'chat' | null>(null);
  const [forward, setForward] = useState<Message | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const pendingText = useRef<{ body: string; replyToId: string | undefined; id: string } | null>(
    null,
  );
  const closure = conversation.closesAt ? Date.parse(conversation.closesAt) : null;
  const closed = Boolean(conversation.readOnly || (closure && now >= closure));
  const canSend = profileReady && !closed && conversation.canSend !== false;
  useEffect(() => {
    const date = Date.parse(query.serverNow ?? conversation.serverNow ?? '');
    if (Number.isFinite(date)) clock.current = { server: date, at: performance.now() };
  }, [query.serverNow, conversation.serverNow]);
  useEffect(() => {
    const timer = window.setInterval(
      () => setNow(clock.current.server + performance.now() - clock.current.at),
      500,
    );
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (nearBottom.current) bottom.current?.scrollIntoView({ block: 'end' });
  }, [lastMessageId]);
  useEffect(() => {
    if (!query.isSuccess) return;
    if (reply) {
      const latest = messages.find((message) => message.id === reply.id);
      if (!latest || latest.deleted) setReply(null);
      else if (latest.body !== reply.body) setReply(latest);
    }
  }, [messages, query.isSuccess, reply]);
  async function refresh() {
    await client.invalidateQueries({ queryKey: ['conversations'] });
  }
  async function action(run: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await run();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not complete the action.');
    } finally {
      setBusy(false);
    }
  }
  async function sendText() {
    const body = draft.trim();
    if (!body || !canSend || send.isPending || recording) return;
    if (
      !pendingText.current ||
      pendingText.current.body !== body ||
      pendingText.current.replyToId !== reply?.id
    )
      pendingText.current = { body, replyToId: reply?.id, id: crypto.randomUUID() };
    setError(null);
    try {
      await send.mutateAsync({
        body,
        conversationId: conversation.id,
        clientId: pendingText.current.id,
        ...(reply ? { replyToId: reply.id } : {}),
      });
      setDraft('');
      setReply(null);
      pendingText.current = null;
      nearBottom.current = true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not send. Your draft is still here.');
    }
  }
  async function clear() {
    if (
      !window.confirm(
        'Clear your whole chat history? Only your view changes. The other participant and platform retain their records. You can undo for 10 seconds.',
      )
    )
      return;
    await action(async () => {
      const result = await profileRequest<{ undoToken: string; undoUntil: string }>(
        `/me/conversations/${conversation.id}/clear`,
        { method: 'POST' },
      );
      player.stop();
      await client.invalidateQueries({ queryKey: ['call-history', conversation.id] });
      setReply(null);
      setEditing(null);
      setUndo(result);
      await client.resetQueries({ queryKey: ['conversations', conversation.id, 'messages'] });
    });
  }
  async function undoClear() {
    if (!undo) return;
    await action(async () => {
      await profileRequest(`/me/conversations/${conversation.id}/clear/undo`, {
        method: 'POST',
        body: JSON.stringify({ undoToken: undo.undoToken }),
      });
      setUndo(null);
      await client.resetQueries({ queryKey: ['conversations', conversation.id, 'messages'] });
    });
  }
  async function deleteMessage(message: Message) {
    await action(async () => {
      await profileRequest(`/me/chat-messages/${message.id}`, { method: 'DELETE' });
      if (player.id === message.id) player.stop();
    });
  }
  async function saveEdit() {
    if (!editing) return;
    await action(async () => {
      await profileRequest(`/me/chat-messages/${editing.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ body: editBody }),
      });
      setEditing(null);
    });
  }
  const remaining = closure ? Math.max(0, closure - now) : 0;

  return {
    canSend,
    calls,
    busy,
    recording,
    clear,
    setReport,
    closure,
    closed,
    remaining,
    undo,
    now,
    undoClear,
    scroll,
    nearBottom,
    query,
    messages,
    setReply,
    setForward,
    setEditing,
    setEditBody,
    deleteMessage,
    bottom,
    error,
    reply,
    sendText,
    draft,
    setDraft,
    send,
    setRecording,
    refresh,
    editing,
    saveEdit,
    editBody,
    report,
    forward,
  };
}
