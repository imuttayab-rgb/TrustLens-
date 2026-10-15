/** Recording states and callbacks shared by the recorder hook and UI. */
export type Phase = 'idle' | 'requesting' | 'recording' | 'paused' | 'preview' | 'sending';
export type VoiceRecorderOptions = {
  conversationId: string;
  disabled: boolean;
  replyToId?: string | undefined;
  onSent: () => void;
  onActivity: (active: boolean) => void;
};
