'use client';
/** Call commands shared across routes; media resources stay in the controller. */
import { createContext, useContext } from 'react';
import type { Context } from './types';
export const CallContext = createContext<Context | null>(null);
export function useVoiceCalls() {
  const value = useContext(CallContext);
  if (!value) throw new Error('VoiceCallProvider is missing');
  return value;
}
