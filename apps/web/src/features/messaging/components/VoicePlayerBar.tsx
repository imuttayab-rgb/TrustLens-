'use client';
/** Floating presentation of playback controls and recoverable errors. */
import { Pause, Play, X } from 'lucide-react';
import type { useVoicePlayback } from '../hooks/use-voice-playback';
import { voiceTime } from '../playback/time';
export function VoicePlayerBar({
  controller,
}: {
  controller: ReturnType<typeof useVoicePlayback>;
}) {
  const { player } = controller;
  const { id, playing, position, duration, speed, error } = player;
  return (
    <>
      {id && (
        <div
          className="fixed bottom-3 left-1/2 z-50 flex w-[min(94vw,440px)] -translate-x-1/2 items-center gap-3 rounded-xl border border-border bg-background p-3 shadow-xl"
          aria-label="Voice player"
        >
          <button
            type="button"
            aria-label={playing ? 'Pause voice' : 'Resume voice'}
            onClick={() => {
              if (playing) player.pause();
              else controller.resume();
            }}
          >
            {playing ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium">
              Voice message · {voiceTime(position)} / {voiceTime(duration)}
            </p>
            <input
              aria-label="Seek voice"
              type="range"
              min={0}
              max={duration || 1}
              step={0.1}
              value={position}
              onChange={(e) => player.seek(Number(e.target.value))}
              className="w-full"
            />
          </div>
          <button type="button" onClick={player.rate} className="text-xs">
            {speed}×
          </button>
          <button type="button" aria-label="Close voice player" onClick={player.stop}>
            <X size={18} />
          </button>
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded bg-background p-3 text-sm text-destructive shadow"
        >
          {error}
          <button className="ml-3 underline" onClick={controller.dismissError}>
            Dismiss
          </button>
        </div>
      )}
    </>
  );
}
