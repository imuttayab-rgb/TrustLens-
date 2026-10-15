'use client';
/** App-level lifetime: navigation must not disconnect an active call. */
import { CallContext } from '../calls/context';
import { CallPanel } from '../components/CallPanel';
import { useVoiceCallController } from '../hooks/use-voice-call-controller';
export function VoiceCallProvider({ children }: { children: React.ReactNode }) {
  const controller = useVoiceCallController();
  return (
    <CallContext.Provider value={controller.value}>
      {children}
      <CallPanel {...controller} />
    </CallContext.Provider>
  );
}
