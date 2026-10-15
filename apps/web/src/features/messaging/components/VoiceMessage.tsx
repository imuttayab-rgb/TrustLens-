'use client';
/** Individual voice-message bubble; playback is owned by the shared provider. */
import { Pause, Play } from 'lucide-react';
import type { Message } from '../hooks/use-messaging';
import { useVoicePlayer } from '../playback/context';
import { voiceTime } from '../playback/time';
export function VoiceMessage({ message, queue }: { message: Message; queue: Message[] }) {
  const player = useVoicePlayer();
  const active = player.id === message.id;
  return (
    <div className="flex min-w-[190px] max-w-full items-center gap-2">
      <button
        type="button"
        aria-label={active && player.playing ? 'Pause voice message' : 'Play voice message'}
        onClick={() => {
          if (active && player.playing) player.pause();
          else void player.play(message, queue);
        }}
        className="border-current/20 rounded-full border p-2"
      >
        {active && player.playing ? <Pause size={17} /> : <Play size={17} />}
      </button>
      <div className="min-w-0 flex-1">
        <div className="flex h-7 items-center gap-[2px]" aria-hidden="true">
          {message.voice?.waveform.map((peak, i) => (
            <span
              key={i}
              className="w-1 rounded-full bg-current opacity-70"
              style={{ height: `${Math.max(8, peak * 100)}%` }}
            />
          ))}
        </div>
        <p className="text-[11px]">
          {voiceTime(active ? player.position : (message.voice?.duration ?? 0))}
        </p>
      </div>
      <button type="button" onClick={player.rate} className="text-xs">
        {player.speed}×
      </button>
    </div>
  );
}
