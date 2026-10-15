'use client';
/** Presentational call controls. Actions and lifecycle are supplied by the controller. */
import {
  ChevronDown,
  ChevronUp,
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  Settings2,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import Link from 'next/link';
import type { OutputPicker } from '../calls/types';
import type { VoiceCallController } from '../hooks/use-voice-call-controller';
export function CallPanel({
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
}: VoiceCallController) {
  return (
    <>
      {(call || preparing || status || error) && (
        <section
          aria-label="Voice call"
          className="fixed bottom-4 left-1/2 z-[80] max-h-[85dvh] w-[min(94vw,440px)] -translate-x-1/2 overflow-y-auto rounded-2xl border border-border bg-background p-4 shadow-2xl"
          role="status"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-brand">{label}</p>
              {call && (
                <>
                  <p className="mt-1 font-semibold">{call.counterpartName}</p>
                  <Link className="text-xs underline" href={`/messages/${call.conversationId}`}>
                    {call.listingTitle}
                  </Link>
                </>
              )}
            </div>
            {call?.owned && (
              <button
                type="button"
                aria-label={minimized ? 'Expand call' : 'Minimize call'}
                aria-expanded={!minimized}
                className="rounded-lg border border-border p-2"
                onClick={() => setMinimized(!minimized)}
              >
                {minimized ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </button>
            )}
            {!call && !preparing && (
              <button
                aria-label="Dismiss call status"
                onClick={() => {
                  setStatus('');
                  setError(null);
                }}
              >
                <X size={18} />
              </button>
            )}
          </div>
          {error && (
            <p role="alert" className="mt-2 text-sm text-red-600">
              {error}
            </p>
          )}
          {quality && <p className="mt-2 text-xs text-amber-700">{quality}</p>}
          {call?.remoteMuted && (
            <p className="mt-2 text-xs">The other person muted their microphone.</p>
          )}
          {call?.canAnswer && !preparing && (
            <div className="mt-3 flex gap-2">
              <button
                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-green-700 px-4 py-2 text-white"
                onClick={() => void answer(call)}
              >
                <Phone size={18} />
                Accept call
              </button>
              <button
                className="rounded-lg bg-red-600 px-4 py-2 text-white"
                onClick={() => void decline()}
              >
                Decline
              </button>
            </div>
          )}
          {(preparing || call?.owned) && (
            <div className="mt-3 flex gap-2">
              {hasMicrophone && (
                <button
                  aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}
                  aria-pressed={muted}
                  className="flex items-center justify-center gap-2 rounded-lg border border-border px-3 py-2 text-sm"
                  onClick={() => void toggleMicrophone()}
                >
                  {muted ? <MicOff size={18} /> : <Mic size={18} />}
                  {muted ? 'Unmute' : 'Mute'}
                </button>
              )}
              <button
                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-white"
                onClick={() => void stop()}
              >
                <PhoneOff size={18} />
                End call
              </button>
            </div>
          )}
          {call?.owned && !minimized && (
            <>
              <div className="mt-2 flex gap-2 text-sm">
                <button
                  type="button"
                  aria-expanded={audioSettings}
                  aria-controls="call-audio-settings"
                  className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-border p-2"
                  onClick={() => setAudioSettings(!audioSettings)}
                >
                  <Settings2 size={17} /> Audio settings
                </button>
                <button
                  type="button"
                  aria-label={soundOff ? 'Unmute call sound' : 'Mute call sound'}
                  aria-pressed={soundOff}
                  className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-border p-2"
                  onClick={toggleSound}
                >
                  {soundOff ? <VolumeX size={17} /> : <Volume2 size={17} />}
                  {soundOff ? 'Sound off' : 'Sound on'}
                </button>
              </div>
              {audioSettings && (
                <div
                  id="call-audio-settings"
                  className="mt-3 space-y-3 rounded-lg border border-border p-3 text-xs"
                >
                  <p className="font-semibold">Speaker / headset and microphone</p>
                  {!hasRoom && (
                    <p>Audio device selection becomes available when the call connects.</p>
                  )}
                  <label className="block">
                    Microphone
                    <select
                      aria-label="Call microphone"
                      value={inputId}
                      disabled={!hasRoom || deviceBusy}
                      className="mt-1 w-full rounded border border-border bg-background p-2 disabled:opacity-50"
                      onChange={(event) => void changeDevice('audioinput', event.target.value)}
                    >
                      <option value="default">System default microphone</option>
                      {devices
                        .filter(
                          (d) => d.kind === 'audioinput' && d.deviceId && d.deviceId !== 'default',
                        )
                        .map((d, i) => (
                          <option key={d.deviceId} value={d.deviceId}>
                            {d.label || `Microphone ${i + 1}`}
                          </option>
                        ))}
                    </select>
                  </label>
                  {'setSinkId' in HTMLMediaElement.prototype ? (
                    <>
                      <label className="block">
                        Speaker / headset
                        <select
                          aria-label="Call speaker"
                          value={outputId}
                          disabled={!hasRoom || deviceBusy}
                          className="mt-1 w-full rounded border border-border bg-background p-2 disabled:opacity-50"
                          onChange={(event) => void changeDevice('audiooutput', event.target.value)}
                        >
                          <option value="default">System default speaker / headset</option>
                          {devices
                            .filter(
                              (d) =>
                                d.kind === 'audiooutput' && d.deviceId && d.deviceId !== 'default',
                            )
                            .map((d, i) => (
                              <option key={d.deviceId} value={d.deviceId}>
                                {d.label || `Speaker / headset ${i + 1}`}
                              </option>
                            ))}
                        </select>
                      </label>
                      {typeof (navigator.mediaDevices as OutputPicker).selectAudioOutput ===
                        'function' && (
                        <button
                          type="button"
                          disabled={!hasRoom || deviceBusy}
                          className="rounded border border-border p-2 disabled:opacity-50"
                          onClick={() => void changeDevice('audiooutput')}
                        >
                          Choose another speaker / headset
                        </button>
                      )}
                      <p className="text-muted-foreground">
                        Only devices allowed by your browser appear here. Connect Bluetooth in your
                        device settings first.
                      </p>
                    </>
                  ) : (
                    <p className="rounded bg-muted p-2">
                      This browser controls the speaker automatically. Use your phone or computer
                      audio settings to choose speaker, earpiece or Bluetooth.
                    </p>
                  )}
                  <button
                    type="button"
                    className="underline"
                    disabled={deviceBusy}
                    onClick={() => void refreshDevices()}
                  >
                    Refresh audio devices
                  </button>
                  {deviceBusy && <p role="status">Changing audio device…</p>}
                  {deviceError && (
                    <p role="alert" className="text-red-600">
                      {deviceError}
                    </p>
                  )}
                  <p className="text-muted-foreground">
                    Use your device volume buttons for loudness. Sound off silences only what you
                    hear; Mute stops your microphone.
                  </p>
                </div>
              )}
            </>
          )}
          {soundOff && (
            <p className="mt-2 text-xs">
              Call sound is off on this device.{minimized ? ' Expand to turn it back on.' : ''}
            </p>
          )}
          {needsPlay && (
            <button
              className="mt-2 w-full rounded border p-2 text-sm"
              onClick={() => void enableAudio()}
            >
              Enable call audio
            </button>
          )}
        </section>
      )}
    </>
  );
}
