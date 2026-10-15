'use client';
/** Owns signalling, media leases, reconnects and resource cleanup for one browser tab.
 * React Query owns server configuration/history; refs own nonserializable media handles.
 * Generation guards prevent late async operations from reviving an ended call.
 */
import { useSession } from '@/lib/auth/use-session';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { LocalAudioTrack, RemoteAudioTrack, Room } from 'livekit-client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { request } from '../calls/api';
import { errorText, reasonLabel } from '../calls/labels';
import type { Call, Config, Health, OutputPicker } from '../calls/types';
import { useVoicePlayer, voiceTime } from '../components/VoicePlayback';
const EMPTY_HEALTH: Health = { quality: 'unknown', receivedBytes: 0, sentBytes: 0, packetsLost: 0 };
export function useVoiceCallController() {
  const { data: session } = useSession();
  const query = useQueryClient();
  const player = useVoicePlayer();
  const config = useQuery({
    queryKey: ['call-config', session?.id],
    queryFn: () => request<Config>('/me/calls/config'),
    enabled: Boolean(session),
    retry: false,
  });
  const [call, setCall] = useState<Call | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [muted, setMuted] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [needsPlay, setNeedsPlay] = useState(false);
  const [quality, setQuality] = useState('');
  const [now, setNow] = useState(Date.now());
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [audioSettings, setAudioSettings] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [inputId, setInputId] = useState('default');
  const [outputId, setOutputId] = useState('default');
  const [deviceBusy, setDeviceBusy] = useState(false);
  const [deviceError, setDeviceError] = useState('');
  const [soundOff, setSoundOff] = useState(false);
  const soundOffRef = useRef(false);
  const deviceWorking = useRef(false);
  const [notifications, setNotifications] = useState(false);
  const pushId = useRef<string | null>(null);
  const device = useRef('');
  const current = useRef<Call | null>(null);
  const room = useRef<Room | null>(null);
  const local = useRef<LocalAudioTrack | null>(null);
  const remote = useRef<RemoteAudioTrack | null>(null);
  const audioNodes = useRef<HTMLMediaElement[]>([]);
  const generation = useRef(0);
  const working = useRef(false);
  const joining = useRef(false);
  const lastContact = useRef(Date.now());
  const reconnectAt = useRef<number | null>(null);
  const pendingId = useRef<string | null>(null);
  const clockOffset = useRef(0);
  const health = useRef<Health>({ ...EMPTY_HEALTH });
  const ringContext = useRef<AudioContext | null>(null);
  const lastAudio = useRef({ bytes: 0, at: Date.now() });
  const applyRef = useRef<(row: Call) => Promise<void>>(async () => {});
  const stopRef = useRef<(failed?: boolean) => Promise<void>>(async () => {});
  const startRef = useRef<(id: string) => Promise<void>>(async () => {});
  const notifyRef = useRef<() => Promise<void>>(async () => {});
  const startStable = useCallback((id: string) => startRef.current(id), []);
  const notifyStable = useCallback(() => notifyRef.current(), []);
  const publish = useCallback((row: Call | null) => {
    if (row) clockOffset.current = Date.parse(row.serverNow) - Date.now();
    current.current = row;
    setCall(row);
  }, []);
  const release = useCallback(() => {
    generation.current += 1;
    const previous = room.current;
    room.current = null;
    if (previous) {
      previous.removeAllListeners();
      void previous.disconnect(true);
    }
    local.current?.stop();
    local.current = null;
    remote.current = null;
    audioNodes.current.forEach((node) => {
      node.pause();
      node.srcObject = null;
      node.remove();
    });
    audioNodes.current = [];
    health.current = { ...EMPTY_HEALTH };
    reconnectAt.current = null;
    joining.current = false;
    setMuted(false);
    setNeedsPlay(false);
    setPreparing(false);
    setDevices([]);
    setInputId('default');
    setOutputId('default');
    setAudioSettings(false);
    setMinimized(false);
    setDeviceBusy(false);
    deviceWorking.current = false;
    setDeviceError('');
    setSoundOff(false);
    soundOffRef.current = false;
    setQuality('');
    working.current = false;
  }, []);
  const action = useCallback(
    (id: string, name: string, extra: Record<string, unknown> = {}) =>
      request<Call>(`/me/calls/${id}/actions`, {
        method: 'POST',
        body: JSON.stringify({ deviceId: device.current, action: name, ...extra }),
      }),
    [],
  );
  async function ended(row: Call) {
    release();
    pendingId.current = null;
    publish(null);
    setStatus(reasonLabel[row.reason ?? 'ended'] ?? 'Call ended');
    await query.invalidateQueries({ queryKey: ['call-history'] });
  }
  async function stop(failed = false) {
    const row = current.current;
    const id = row?.owned ? row.id : pendingId.current;
    release();
    publish(null);
    pendingId.current = null;
    setStatus(failed ? 'Connection lost. Please try calling again.' : 'Call ended');
    try {
      if (id) await action(id, failed ? 'failed' : 'end');
      else if (row?.canAnswer) await action(row.id, 'reject');
    } catch {
      setError('Audio stopped on this device. The call will close when the connection times out.');
    }
    void query.invalidateQueries({ queryKey: ['call-history'] });
  }
  stopRef.current = stop;
  async function refreshDevices() {
    const token = generation.current;
    try {
      const list = await navigator.mediaDevices.enumerateDevices();
      if (token === generation.current) setDevices(list);
    } catch {
      if (token === generation.current)
        setDeviceError(
          'Could not list audio devices. Check browser permissions, then refresh devices.',
        );
    }
  }
  async function changeDevice(kind: 'audioinput' | 'audiooutput', id?: string) {
    const live = room.current;
    const token = generation.current;
    if (!live || deviceWorking.current) return;
    deviceWorking.current = true;
    setDeviceBusy(true);
    setDeviceError('');
    try {
      // The browser picker must run directly from the click, before another await.
      const selected =
        id ?? (await (navigator.mediaDevices as OutputPicker).selectAudioOutput?.())?.deviceId;
      if (token !== generation.current || room.current !== live) return;
      if (!selected)
        throw new Error('Choose an audio device from the list or your device settings.');
      const changed = await live.switchActiveDevice(kind, selected);
      if (token !== generation.current || room.current !== live) return;
      if (!changed)
        throw new Error(
          'The audio device could not be changed. Your previous selection is still in use.',
        );
      if (kind === 'audioinput') setInputId(live.getActiveDevice(kind) || selected);
      else setOutputId(live.getActiveDevice(kind) || selected);
      await refreshDevices();
    } catch (e) {
      if (token === generation.current) {
        setDeviceError(
          e instanceof Error && e.name === 'NotAllowedError'
            ? 'Audio device permission was not granted. Allow access in browser settings or choose another device.'
            : e instanceof Error
              ? e.message
              : 'Could not change the audio device. Please try again.',
        );
      }
    } finally {
      if (token === generation.current) {
        deviceWorking.current = false;
        setDeviceBusy(false);
      }
    }
  }
  function toggleSound() {
    soundOffRef.current = !soundOffRef.current;
    audioNodes.current.forEach((node) => {
      node.muted = soundOffRef.current;
    });
    setSoundOff(soundOffRef.current);
  }
  async function microphone(token: number) {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)
      throw new Error('Calling needs HTTPS or localhost and microphone access.');
    const sdk = await import('livekit-client');
    const track = await sdk.createLocalAudioTrack({
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    });
    if (token !== generation.current) {
      track.stop();
      throw new Error('Call cancelled.');
    }
    local.current = track;
    player.stop();
    track.mediaStreamTrack.addEventListener(
      'ended',
      () => {
        if (local.current === track) {
          setError('Microphone disconnected.');
          void stopRef.current(true);
        }
      },
      { once: true },
    );
    setInputId(track.mediaStreamTrack.getSettings().deviceId || 'default');
    // Device enumeration failure must not discard a usable microphone.
    await refreshDevices();
    return sdk;
  }
  async function join(row: Call, token: number) {
    if (room.current || joining.current || !local.current || !row.owned) return;
    joining.current = true;
    setStatus('Connecting audio…');
    try {
      const [sdk, access] = await Promise.all([
        import('livekit-client'),
        request<{ url: string; token: string }>(`/me/calls/${row.id}/join`, {
          method: 'POST',
          body: JSON.stringify({ deviceId: device.current }),
        }),
      ]);
      if (token !== generation.current) return;
      const live = new sdk.Room({ disconnectOnPageLeave: true });
      room.current = live;
      live.on(sdk.RoomEvent.TrackSubscribed, (track) => {
        if (token !== generation.current || track.kind !== sdk.Track.Kind.Audio) return;
        reconnectAt.current = null;
        remote.current = track as RemoteAudioTrack;
        const element = track.attach();
        element.muted = soundOffRef.current;
        audioNodes.current.push(element);
        element.autoplay = true;
        void element.play().catch(() => setNeedsPlay(true));
        lastAudio.current = { bytes: 0, at: Date.now() };
        setStatus('Connected');
      });
      live.on(sdk.RoomEvent.TrackUnsubscribed, (track) => {
        track.detach().forEach((element) => {
          audioNodes.current = audioNodes.current.filter((node) => node !== element);
          element.remove();
        });
        if (remote.current === track) remote.current = null;
      });
      live.on(sdk.RoomEvent.Reconnecting, () => {
        reconnectAt.current ??= Date.now();
        setStatus('Reconnecting audio…');
      });
      live.on(sdk.RoomEvent.SignalReconnecting, () => {
        reconnectAt.current ??= Date.now();
        setStatus('Reconnecting…');
      });
      live.on(sdk.RoomEvent.Reconnected, () => {
        reconnectAt.current = null;
        lastAudio.current.at = Date.now();
        setStatus('Connected');
      });
      live.on(sdk.RoomEvent.Disconnected, () => {
        if (token === generation.current) void stopRef.current(true);
      });
      live.on(sdk.RoomEvent.ParticipantDisconnected, () => {
        reconnectAt.current ??= Date.now();
        setStatus('Waiting for the other person to reconnect…');
      });
      live.on(sdk.RoomEvent.AudioPlaybackStatusChanged, () => setNeedsPlay(!live.canPlaybackAudio));
      live.on(sdk.RoomEvent.ActiveDeviceChanged, (kind, id) => {
        if (token !== generation.current) return;
        if (kind === 'audioinput') setInputId(id || 'default');
        if (kind === 'audiooutput') setOutputId(id || 'default');
      });
      live.on(sdk.RoomEvent.ConnectionQualityChanged, (value, participant) => {
        if (participant.isLocal) health.current.quality = value;
        setQuality(
          String(value) === 'poor' || String(value) === 'lost'
            ? 'Weak connection — try a stronger Wi-Fi or mobile signal.'
            : '',
        );
      });
      await live.connect(access.url, access.token, {
        autoSubscribe: true,
        maxRetries: 1,
        websocketTimeout: 8000,
        peerConnectionTimeout: 10000,
      });
      if (token !== generation.current || !local.current) {
        await live.disconnect(true);
        return;
      }
      await live.localParticipant.publishTrack(
        local.current as Parameters<Room['localParticipant']['publishTrack']>[0],
        {
          source: sdk.Track.Source.Microphone,
          dtx: false,
          audioPreset: sdk.AudioPresets.speech,
        },
      );
      lastContact.current = Date.now();
      setInputId(
        live.getActiveDevice('audioinput') ||
          local.current.mediaStreamTrack.getSettings().deviceId ||
          'default',
      );
      setOutputId(live.getActiveDevice('audiooutput') || 'default');
      void live.startAudio().catch(() => setNeedsPlay(true));
    } catch (e) {
      if (token === generation.current) {
        setError(errorText(e));
        await stopRef.current(true);
      }
    } finally {
      if (token === generation.current) joining.current = false;
    }
  }
  async function start(conversationId: string) {
    if (!session || !config.data?.enabled || current.current || working.current) return;
    working.current = true;
    setPreparing(true);
    setMinimized(false);
    setError(null);
    setStatus('Checking microphone…');
    const token = ++generation.current;
    const id = crypto.randomUUID();
    pendingId.current = id;
    try {
      await microphone(token);
      if (token !== generation.current) return;
      const row = await request<Call>('/me/calls', {
        method: 'POST',
        body: JSON.stringify({ conversationId, callId: id, deviceId: device.current }),
      });
      if (token !== generation.current) {
        await action(id, 'end');
        return;
      }
      lastContact.current = Date.now();
      publish(row);
    } catch (e) {
      if (token === generation.current) {
        release();
        publish(null);
        pendingId.current = null;
        setStatus('');
        setError(errorText(e));
        void action(id, 'failed').catch(() => {});
      }
    } finally {
      if (token === generation.current) {
        working.current = false;
        setPreparing(false);
      }
    }
  }
  startRef.current = start;
  async function answer(row: Call) {
    if (working.current) return;
    working.current = true;
    setPreparing(true);
    setMinimized(false);
    setError(null);
    setStatus('Checking microphone…');
    const token = ++generation.current;
    try {
      await microphone(token);
      if (token !== generation.current) return;
      const accepted = await action(row.id, 'accept');
      if (token !== generation.current) {
        if (accepted.owned) await action(row.id, 'end');
        return;
      }
      if (accepted.state === 'ended') {
        await ended(accepted);
        return;
      }
      publish(accepted);
      pendingId.current = accepted.id;
      lastContact.current = Date.now();
      working.current = false;
      setPreparing(false);
      await join(accepted, token);
    } catch (e) {
      if (token === generation.current) {
        const owned = current.current?.owned;
        release();
        publish(null);
        pendingId.current = null;
        setError(errorText(e));
        setStatus('');
        if (owned) void action(row.id, 'failed').catch(() => {});
      }
    } finally {
      if (token === generation.current) {
        working.current = false;
        setPreparing(false);
      }
    }
  }
  applyRef.current = async (row) => {
    if (row.state === 'ended') {
      await ended(row);
      return;
    }
    publish(row);
    if (row.owned && (row.state === 'connecting' || row.state === 'active'))
      void join(row, generation.current);
  };
  useEffect(() => {
    device.current = crypto.randomUUID();
    return release;
  }, [release]);
  useEffect(() => {
    if (!session?.id || !config.data?.enabled) {
      release();
      publish(null);
      return;
    }
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    async function tick() {
      const token = generation.current;
      const row = current.current;
      try {
        if (!working.current) {
          if (row?.owned && local.current) {
            const result = await action(row.id, 'sync', {
              connected: String(room.current?.state) === 'connected' && Boolean(remote.current),
              muted: local.current.isMuted,
              health: health.current,
            });
            if (!disposed && token === generation.current) {
              lastContact.current = Date.now();
              await applyRef.current(result);
            }
          } else {
            let result = await request<Call | null>(`/me/calls/active?deviceId=${device.current}`);
            if (!disposed && token === generation.current && !working.current) {
              publish(result);
              if (result?.canAnswer && result.state === 'calling') {
                result = await action(result.id, 'ring');
                if (!disposed && token === generation.current && !working.current) publish(result);
              }
            }
          }
        }
      } catch {
        if (!disposed && row?.owned && token === generation.current) {
          setStatus('Reconnecting to calling service…');
          if (Date.now() - lastContact.current > 20000) void stopRef.current(true);
        }
      }
      if (!disposed)
        timer = setTimeout(() => void tick(), current.current || working.current ? 1000 : 3000);
    }
    void tick();
    return () => {
      disposed = true;
      clearTimeout(timer);
      const row = current.current;
      if (row?.owned) void action(row.id, 'end').catch(() => {});
      release();
      publish(null);
    };
  }, [session?.id, config.data?.enabled, action, release, publish]);
  useEffect(() => {
    let measuring = false;
    const timer = setInterval(() => {
      if (current.current?.connectedAt) setNow(Date.now() + clockOffset.current);
      if (reconnectAt.current && Date.now() - reconnectAt.current > 20000)
        void stopRef.current(true);
      if (!room.current || measuring) return;
      measuring = true;
      void Promise.all([local.current?.getRTCStatsReport(), remote.current?.getRTCStatsReport()])
        .then(([sent, received]) => {
          sent?.forEach((stat: RTCOutboundRtpStreamStats) => {
            if (stat.type === 'outbound-rtp' && stat.kind === 'audio')
              health.current.sentBytes = stat.bytesSent ?? 0;
          });
          received?.forEach((stat: RTCInboundRtpStreamStats) => {
            if (stat.type === 'inbound-rtp' && stat.kind === 'audio') {
              health.current.receivedBytes = stat.bytesReceived ?? 0;
              health.current.packetsLost = Math.max(0, stat.packetsLost ?? 0);
            }
          });
          if (
            health.current.receivedBytes !== lastAudio.current.bytes ||
            current.current?.remoteMuted ||
            String(room.current?.state) !== 'connected'
          )
            lastAudio.current = { bytes: health.current.receivedBytes, at: Date.now() };
          else if (remote.current && Date.now() - lastAudio.current.at > 10000)
            setQuality(
              'No incoming audio data. Check your connection or ask the other person to check their microphone.',
            );
        })
        .catch(() => {})
        .finally(() => {
          measuring = false;
        });
    }, 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const update = () => {
      const token = generation.current;
      if (local.current)
        void navigator.mediaDevices
          .enumerateDevices()
          .then((list) => {
            if (token === generation.current) setDevices(list);
          })
          .catch(() => {});
    };
    navigator.mediaDevices?.addEventListener('devicechange', update);
    return () => navigator.mediaDevices?.removeEventListener('devicechange', update);
  }, []);
  useEffect(() => {
    if (!call?.canAnswer) return;
    const ring = () => {
      try {
        const ctx = ringContext.current ?? new AudioContext();
        ringContext.current = ctx;
        if (ctx.state !== 'running') return;
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.frequency.value = 520;
        gain.gain.value = 0.06;
        oscillator.connect(gain);
        gain.connect(ctx.destination);
        oscillator.start();
        oscillator.stop(ctx.currentTime + 0.35);
      } catch {
        /* Incoming panel remains visible when browser audio needs a tap. */
      }
    };
    ring();
    const timer = setInterval(ring, 2200);
    return () => {
      clearInterval(timer);
      void ringContext.current?.close();
      ringContext.current = null;
    };
  }, [call?.canAnswer]);
  const sessionId = session?.id;
  const sessionLoading = session === undefined;
  useEffect(() => {
    if (sessionLoading) return;
    let disposed = false;
    setNotifications(false);
    pushId.current = null;
    if (!('serviceWorker' in navigator)) return;
    void navigator.serviceWorker
      .getRegistration('/')
      .then(async (registration) => {
        const sub = await registration?.pushManager.getSubscription();
        if (!sub) return;
        if (!sessionId) {
          await sub.unsubscribe();
          return;
        }
        const value = sub.toJSON();
        try {
          const saved = await request<{ id: string }>('/me/calls/push', {
            method: 'POST',
            body: JSON.stringify({ endpoint: value.endpoint, keys: value.keys }),
          });
          if (!disposed) {
            pushId.current = saved.id;
            setNotifications(true);
          }
        } catch {
          // Do not associate another account's existing browser subscription.
          // Leave it in place on a network outage; the user can retry explicitly.
        }
      })
      .catch(() => {});
    return () => {
      disposed = true;
    };
  }, [sessionId, sessionLoading]);
  notifyRef.current = async () => {
    try {
      if (
        !session ||
        !config.data?.pushPublicKey ||
        !('serviceWorker' in navigator) ||
        !('PushManager' in window)
      )
        throw new Error(
          'Push notifications are unavailable here. On iPhone, add TrustLens to your Home Screen and open it there.',
        );
      const registration = await navigator.serviceWorker.register('/call-sw.js', { scope: '/' });
      await navigator.serviceWorker.ready;
      const previous = await registration.pushManager.getSubscription();
      if (notifications && previous) {
        if (pushId.current) await request(`/me/calls/push/${pushId.current}`, { method: 'DELETE' });
        await previous.unsubscribe();
        pushId.current = null;
        setNotifications(false);
        return;
      }
      if ((await Notification.requestPermission()) !== 'granted')
        throw new Error(
          'Allow notifications in your browser settings to receive call invitations.',
        );
      const base = config.data.pushPublicKey.replace(/-/g, '+').replace(/_/g, '/');
      const key = Uint8Array.from(atob(base + '='.repeat((4 - (base.length % 4)) % 4)), (char) =>
        char.charCodeAt(0),
      );
      // A rejected old-account registration must obtain a fresh push endpoint.
      if (previous) await previous.unsubscribe();
      const sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: key,
      });
      const value = sub.toJSON();
      const saved = await request<{ id: string }>('/me/calls/push', {
        method: 'POST',
        body: JSON.stringify({ endpoint: value.endpoint, keys: value.keys }),
      });
      pushId.current = saved.id;
      setNotifications(true);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  };
  // Media mutations stay in the lifecycle controller; views receive commands only.
  async function toggleMicrophone() {
    const track = local.current;
    if (!track) return;
    try {
      await (track.isMuted ? track.unmute() : track.mute());
      if (local.current === track) setMuted(track.isMuted);
    } catch (e) {
      setError(errorText(e));
    }
  }
  async function enableAudio() {
    try {
      await room.current?.startAudio();
      setNeedsPlay(false);
    } catch (e) {
      setError(errorText(e));
    }
  }
  async function decline() {
    if (!call?.canAnswer) return;
    try {
      await ended(await action(call.id, 'reject'));
    } catch (e) {
      setError(errorText(e));
    }
  }
  const hasMicrophone = Boolean(local.current);
  const hasRoom = Boolean(room.current);
  const duration = call?.connectedAt ? Math.max(0, (now - Date.parse(call.connectedAt)) / 1000) : 0;
  const busy = Boolean(call || preparing);
  const value = useMemo(
    () => ({
      busy,
      available: Boolean(config.data?.enabled),
      start: startStable,
      notifications,
      toggleNotifications: notifyStable,
      pushAvailable: Boolean(config.data?.pushPublicKey),
    }),
    [
      busy,
      config.data?.enabled,
      config.data?.pushPublicKey,
      startStable,
      notifications,
      notifyStable,
    ],
  );
  const label = call?.canAnswer
    ? 'Incoming voice call'
    : call && !call.owned
      ? 'Call open on another tab / device'
      : call?.state === 'calling'
        ? 'Calling…'
        : call?.state === 'ringing'
          ? 'Ringing…'
          : call?.state === 'active'
            ? status === 'Connected'
              ? `Connected · ${voiceTime(duration)}`
              : status || `Connected · ${voiceTime(duration)}`
            : preparing
              ? 'Checking microphone…'
              : call
                ? 'Connecting audio…'
                : status;

  return {
    value,
    call,
    preparing,
    status,
    error,
    label,
    minimized,
    setMinimized,
    setStatus,
    setError,
    quality,
    answer,
    decline,
    hasMicrophone,
    muted,
    toggleMicrophone,
    stop,
    audioSettings,
    setAudioSettings,
    soundOff,
    toggleSound,
    hasRoom,
    inputId,
    deviceBusy,
    changeDevice,
    devices,
    outputId,
    refreshDevices,
    deviceError,
    needsPlay,
    enableAudio,
  };
}
export type VoiceCallController = ReturnType<typeof useVoiceCallController>;
