'use client';
/** Recording controls and preview; capture/upload logic is isolated in useVoiceRecorder. */
import { LockKeyhole, Mic, Pause, Play, Send, Square, Trash2 } from 'lucide-react';
import { useVoiceRecorder } from '../hooks/use-voice-recorder';
import type { VoiceRecorderOptions } from '../recording/types';
import { RecorderGesture } from './RecorderGesture';
import { voiceTime } from './VoicePlayback';
export function VoiceRecorder(options: VoiceRecorderOptions) {
  const { disabled } = options;
  const {
    phase,
    origin,
    start,
    lockRef,
    locked,
    setLocked,
    stop,
    level,
    seconds,
    pause,
    preview,
    send,
    progress,
    error,
  } = useVoiceRecorder(options);
  return (
    <div
      className={
        phase === 'idle' ? 'shrink-0' : 'w-full rounded-xl border border-border bg-muted/40 p-3'
      }
    >
      {
        <button
          type="button"
          disabled={disabled}
          aria-label="Record voice message"
          title="Hold to record, release to preview. Tap for hands-free recording."
          className={
            phase === 'idle'
              ? 'grid h-10 w-10 touch-none place-items-center rounded-full border border-border text-brand disabled:opacity-40'
              : 'sr-only'
          }
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            e.currentTarget.setPointerCapture(e.pointerId);
            origin.current = { x: e.clientX, y: e.clientY, at: performance.now() };
            void start();
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              lockRef.current = true;
              void start();
            }
          }}
        >
          <Mic size={20} />
        </button>
      }
      {/* A captured pointer stays on the original button. Window handlers below finish gestures. */}
      <RecorderGesture
        origin={origin}
        phase={phase}
        locked={lockRef}
        onLock={() => {
          lockRef.current = true;
          setLocked(true);
        }}
        onStop={stop}
      />
      {phase === 'requesting' && (
        <p className="text-xs">
          Waiting for microphone permission…{' '}
          <button type="button" onClick={() => stop(true)} className="underline">
            Cancel
          </button>
        </p>
      )}
      {(phase === 'recording' || phase === 'paused') && (
        <>
          <div className="flex items-center gap-3">
            <span
              className="h-3 w-3 rounded-full bg-red-500"
              style={{ transform: `scale(${1 + level})` }}
            />
            <span className="text-sm tabular-nums">{voiceTime(seconds)} / 5:00</span>
            <span className="flex-1 text-xs text-muted-foreground">
              {locked ? 'Hands-free' : 'Slide left to cancel · up to lock'}
            </span>
            {locked && <LockKeyhole size={14} />}
          </div>
          <div className="mt-3 flex items-center gap-3">
            <button type="button" onClick={() => stop(true)} aria-label="Cancel recording">
              <Trash2 size={19} />
            </button>
            <button
              type="button"
              onClick={pause}
              aria-label={phase === 'paused' ? 'Resume recording' : 'Pause recording'}
            >
              {phase === 'paused' ? <Play size={19} /> : <Pause size={19} />}
            </button>
            <button
              type="button"
              onClick={() => stop()}
              className="ml-auto flex items-center gap-2 rounded bg-brand px-3 py-2 text-xs text-white"
            >
              <Square size={14} />
              Preview
            </button>
          </div>
        </>
      )}
      {(phase === 'preview' || phase === 'sending') && preview && (
        <>
          {/* User-created private recording; no transcript is generated. */}
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <audio controls src={preview} preload="metadata" className="h-10 w-full" />
          <div className="mt-2 flex items-center gap-3">
            <button
              type="button"
              disabled={phase === 'sending'}
              onClick={() => stop(true)}
              className="flex items-center gap-1 text-xs"
            >
              <Trash2 size={16} />
              Discard / record again
            </button>
            <button
              type="button"
              disabled={disabled || phase === 'sending'}
              onClick={() => void send()}
              className="ml-auto flex items-center gap-2 rounded bg-brand px-3 py-2 text-xs text-white disabled:opacity-40"
            >
              <Send size={15} />
              {phase === 'sending'
                ? progress === 100
                  ? 'Processing…'
                  : `Uploading ${progress}%`
                : 'Send voice'}
            </button>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Preview before sending. Keep this chat open until sent.
          </p>
        </>
      )}
      {error && (
        <p role="alert" className="mt-2 max-w-sm text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
