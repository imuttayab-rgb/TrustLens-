'use client';
/** Owns audio lifetime, queue, speed, remembered positions and cancellation of stale fetches. */
import { profileRequest } from '@/features/profile';
import { useSession } from '@/lib/auth/use-session';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Message } from '../hooks/use-messaging';
import { fetchVoiceBlob } from '../lib/chat-transport';

import type { Player } from '../playback/types';
export function useVoicePlayback() {
  const { data: session } = useSession();
  const client = useQueryClient();
  const audio = useRef<HTMLAudioElement | null>(null);
  const current = useRef<Message | null>(null);
  const pending = useRef(0);
  const queue = useRef<Message[]>([]);
  const positions = useRef(new Map<string, number>());
  const url = useRef<string | null>(null);
  const [id, setId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const stop = useCallback(() => {
    pending.current += 1;
    audio.current?.pause();
    if (audio.current) {
      audio.current.removeAttribute('src');
      audio.current.load();
    }
    if (url.current) URL.revokeObjectURL(url.current);
    url.current = null;
    current.current = null;
    queue.current = [];
    setId(null);
    setPlaying(false);
  }, []);
  const playRef = useRef<(message: Message, list?: Message[]) => Promise<void>>(async () => {});
  async function play(message: Message, list?: Message[]) {
    if (!audio.current) return;
    setError(null);
    if (list) queue.current = list.filter((item) => item.kind === 'voice' && !item.deleted);
    if (current.current?.id === message.id && url.current) {
      try {
        await audio.current.play();
      } catch {
        setError('Tap play to resume audio.');
      }
      return;
    }
    const generation = ++pending.current;
    audio.current.pause();
    try {
      const blob = await fetchVoiceBlob(`/me/chat-messages/${message.id}/audio`);
      if (generation !== pending.current || !audio.current) return;
      if (url.current) URL.revokeObjectURL(url.current);
      url.current = URL.createObjectURL(blob);
      current.current = message;
      audio.current.src = url.current;
      audio.current.playbackRate = speed;
      setId(message.id);
      setPosition(positions.current.get(message.id) ?? 0);
      setDuration(message.voice?.duration ?? 0);
      await audio.current.play();
    } catch (e) {
      if (generation === pending.current)
        setError(e instanceof Error ? e.message : 'Could not play audio.');
    }
  }
  playRef.current = play;
  useEffect(() => {
    const el = new Audio();
    audio.current = el;
    const metadata = () => {
      if (current.current) el.currentTime = positions.current.get(current.current.id) ?? 0;
      setDuration(
        Number.isFinite(el.duration) ? el.duration : (current.current?.voice?.duration ?? 0),
      );
    };
    const time = () => {
      setPosition(el.currentTime);
      if (current.current) positions.current.set(current.current.id, el.currentTime);
    };
    const started = () => {
      setPlaying(true);
      const message = current.current;
      if (message)
        void profileRequest(`/me/chat-messages/${message.id}/played`, { method: 'POST' })
          .then(() =>
            client.invalidateQueries({
              queryKey: ['conversations', message.conversationId, 'messages'],
            }),
          )
          .catch(() => {});
    };
    const paused = () => setPlaying(false);
    const ended = () => {
      setPlaying(false);
      if (!current.current) return;
      positions.current.set(current.current.id, 0);
      const index = queue.current.findIndex((item) => item.id === current.current?.id);
      const next = index >= 0 ? queue.current[index + 1] : undefined;
      if (next) void playRef.current(next);
    };
    el.addEventListener('loadedmetadata', metadata);
    el.addEventListener('timeupdate', time);
    el.addEventListener('playing', started);
    el.addEventListener('pause', paused);
    el.addEventListener('ended', ended);
    return () => {
      pending.current += 1;
      el.pause();
      el.src = '';
      if (url.current) URL.revokeObjectURL(url.current);
      audio.current = null;
    };
  }, [client]);
  useEffect(() => {
    stop();
    positions.current.clear();
  }, [session?.id, stop]);
  // Revoke in-memory playback when polling reports delete/clear; keep playing on route changes.
  useEffect(
    () =>
      client.getQueryCache().subscribe((event) => {
        const message = current.current;
        if (!message || event.type !== 'updated') return;
        const key: readonly unknown[] = event.query.queryKey as readonly unknown[];
        if (
          key[0] !== 'conversations' ||
          key[1] !== message.conversationId ||
          key[2] !== 'messages'
        )
          return;
        const data = event.query.state.data as { pages?: { items: Message[] }[] } | undefined;
        const fresh = data?.pages
          ?.flatMap((page) => page.items)
          .find((item) => item.id === message.id);
        if (fresh?.deleted) stop();
      }),
    [client, stop],
  );
  const player: Player = {
    id,
    playing,
    position,
    duration,
    speed,
    error,
    play,
    pause: () => audio.current?.pause(),
    seek: (time) => {
      if (audio.current) audio.current.currentTime = time;
    },
    rate: () => {
      const next = speed === 1 ? 1.5 : speed === 1.5 ? 2 : 1;
      setSpeed(next);
      if (audio.current) audio.current.playbackRate = next;
    },
    stop,
  };
  return {
    player,
    resume: () => {
      if (current.current) void play(current.current);
    },
    dismissError: () => setError(null),
  };
}
