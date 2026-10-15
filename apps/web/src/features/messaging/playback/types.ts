/** Shared state and commands for one app-wide voice-message player. */
import type { Message } from '../hooks/use-messaging';
export type Player = {
  id: string | null;
  playing: boolean;
  position: number;
  duration: number;
  speed: number;
  error: string | null;
  play: (message: Message, queue?: Message[]) => Promise<void>;
  pause: () => void;
  seek: (time: number) => void;
  rate: () => void;
  stop: () => void;
};
