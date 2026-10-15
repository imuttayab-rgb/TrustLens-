'use client';
/** Creates the playback controller once, above the route boundary. */
import { VoiceContext } from '../playback/context';
import { useVoicePlayback } from '../hooks/use-voice-playback';
import { VoicePlayerBar } from '../components/VoicePlayerBar';
export function VoicePlaybackProvider({ children }: { children: React.ReactNode }) {
  const controller = useVoicePlayback();
  return (
    <VoiceContext.Provider value={controller.player}>
      {children}
      <VoicePlayerBar controller={controller} />
    </VoiceContext.Provider>
  );
}
