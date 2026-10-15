'use client';
/** Pointer capture translates drag/release into recording commands; no upload or audio logic. */
import { useEffect, useRef } from 'react';
import type { Phase } from '../recording/types';
export function RecorderGesture({
  origin,
  phase,
  locked,
  onLock,
  onStop,
}: {
  origin: React.RefObject<{ x: number; y: number; at: number } | null>;
  phase: Phase;
  locked: React.RefObject<boolean>;
  onLock: () => void;
  onStop: (discard?: boolean) => void;
}) {
  const callbacks = useRef({ onLock, onStop });
  callbacks.current = { onLock, onStop };
  useEffect(() => {
    function move(e: PointerEvent) {
      if (!origin.current || locked.current) return;
      if (origin.current.x - e.clientX > 90) {
        origin.current = null;
        callbacks.current.onStop(true);
      } else if (origin.current.y - e.clientY > 70) callbacks.current.onLock();
    }
    function up() {
      if (!origin.current) return;
      const held = performance.now() - origin.current.at;
      origin.current = null;
      if (locked.current) return;
      if (held > 450 && phase !== 'requesting') callbacks.current.onStop();
      else callbacks.current.onLock();
    }
    function cancel() {
      origin.current = null;
      if (!locked.current) callbacks.current.onStop(true);
    }
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', cancel);
    return () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', cancel);
    };
  }, [phase, origin, locked]);
  return null;
}
