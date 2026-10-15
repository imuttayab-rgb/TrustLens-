/** Signalling contracts and serializable call UI state. */
export type Call = {
  id: string;
  conversationId: string;
  direction: 'incoming' | 'outgoing';
  counterpartName: string;
  listingTitle: string;
  state: 'calling' | 'ringing' | 'connecting' | 'active' | 'ended';
  reason: string | null;
  createdAt: string;
  connectedAt: string | null;
  endedAt: string | null;
  serverNow: string;
  owned: boolean;
  canAnswer: boolean;
  remoteMuted: boolean;
};
export type Config = { enabled: boolean; pushPublicKey: string };
export type OutputPicker = MediaDevices & { selectAudioOutput?: () => Promise<MediaDeviceInfo> };
export type Health = {
  quality: 'unknown' | 'excellent' | 'good' | 'poor' | 'lost';
  receivedBytes: number;
  sentBytes: number;
  packetsLost: number;
};
export type Context = {
  busy: boolean;
  available: boolean;
  start: (id: string) => Promise<void>;
  notifications: boolean;
  toggleNotifications: () => Promise<void>;
  pushAvailable: boolean;
};
