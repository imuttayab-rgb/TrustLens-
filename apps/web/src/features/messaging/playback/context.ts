'use client';
/** Playback survives page navigation because this context belongs to the app layout. */
import { createContext, useContext } from 'react';
import type { Player } from './types';
export const VoiceContext = createContext<Player | null>(null);
export function useVoicePlayer() {
  const context = useContext(VoiceContext);
  if (!context) throw new Error('VoicePlaybackProvider is required');
  return context;
}
