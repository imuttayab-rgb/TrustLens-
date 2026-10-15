'use client';
/** Captures microphone audio, owns permission/cancel races, and retries uploads with one idempotency key. */
import { useEffect, useRef, useState } from 'react';
import { uploadVoice } from '../lib/chat-transport';
import type { Phase, VoiceRecorderOptions } from '../recording/types';
export function useVoiceRecorder({
  conversationId,
  disabled,
  replyToId,
  onSent,
  onActivity,
}: VoiceRecorderOptions) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [seconds, setSeconds] = useState(0);
  const [locked, setLocked] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const context = useRef<AudioContext | null>(null);
  const analyser = useRef<AnalyserNode | null>(null);
  const chunks = useRef<Blob[]>([]);
  const blob = useRef<Blob | null>(null);
  const clientId = useRef('');
  const generation = useRef(0);
  const cancelled = useRef(false);
  const origin = useRef<{ x: number; y: number; at: number } | null>(null);
  const lockRef = useRef(false);
  const phaseRef = useRef<Phase>('idle');
  const elapsed = useRef(0);
  const startAt = useRef(0);
  const active = useRef(onActivity);
  active.current = onActivity;
  function transition(next: Phase) {
    phaseRef.current = next;
    setPhase(next);
    active.current(next !== 'idle');
  }
  function release() {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    void context.current?.close().catch(() => {});
    context.current = null;
    analyser.current = null;
  }
  function stop(discard = false) {
    if (phaseRef.current === 'sending') return;
    cancelled.current = discard;
    if (discard) {
      generation.current += 1;
      blob.current = null;
      setPreview(null);
      transition('idle');
    }
    const current = recorder.current;
    if (current && current.state !== 'inactive') current.stop();
    else release();
  }
  const stopRef = useRef(stop);
  stopRef.current = stop;
  useEffect(() => {
    if (!disabled) return;
    if (phaseRef.current === 'recording' || phaseRef.current === 'paused') stopRef.current(false);
    else if (phaseRef.current === 'requesting') stopRef.current(true);
  }, [disabled]);
  async function start() {
    if (disabled || phaseRef.current !== 'idle') return;
    setError(null);
    cancelled.current = false;
    chunks.current = [];
    elapsed.current = 0;
    setSeconds(0);
    lockRef.current = false;
    setLocked(false);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Voice recording needs a supported browser on HTTPS or localhost.');
      return;
    }
    const version = ++generation.current;
    transition('requesting');
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      if (version !== generation.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = media;
      const type = [
        'audio/webm;codecs=opus',
        'audio/mp4',
        'audio/ogg;codecs=opus',
        'audio/webm',
      ].find((value) => MediaRecorder.isTypeSupported(value));
      const current = new MediaRecorder(
        media,
        type ? { mimeType: type, audioBitsPerSecond: 48_000 } : undefined,
      );
      recorder.current = current;
      current.ondataavailable = (event) => {
        if (event.data.size) chunks.current.push(event.data);
      };
      current.onerror = () => {
        setError('Recording stopped unexpectedly. Please try again.');
        stop(true);
      };
      current.onstop = () => {
        release();
        if (cancelled.current || version !== generation.current) return;
        const recording = new Blob(chunks.current, { type: current.mimeType });
        if (!recording.size) {
          setError('No audio was captured. Please try again.');
          transition('idle');
          return;
        }
        blob.current = recording;
        clientId.current = crypto.randomUUID();
        setPreview(URL.createObjectURL(recording));
        transition('preview');
      };
      try {
        const ac = new AudioContext();
        context.current = ac;
        const meter = ac.createAnalyser();
        meter.fftSize = 256;
        ac.createMediaStreamSource(media).connect(meter);
        analyser.current = meter;
      } catch {
        /* Recording works without a visual meter. */
      }
      startAt.current = performance.now();
      current.start(250);
      transition('recording');
    } catch (e) {
      release();
      if (version === generation.current) {
        transition('idle');
        setError(
          e instanceof Error && e.name === 'NotAllowedError'
            ? 'Microphone permission was denied. Allow it in your browser settings and try again.'
            : 'Could not open the microphone. Check that it is connected and available.',
        );
      }
    }
  }
  function pause() {
    if (!recorder.current) return;
    if (recorder.current.state === 'recording') {
      elapsed.current += (performance.now() - startAt.current) / 1000;
      recorder.current.pause();
      transition('paused');
    } else if (recorder.current.state === 'paused') {
      startAt.current = performance.now();
      recorder.current.resume();
      transition('recording');
    }
  }
  useEffect(() => {
    if (phase !== 'recording') return;
    const timer = window.setInterval(() => {
      const time = elapsed.current + (performance.now() - startAt.current) / 1000;
      setSeconds(time);
      if (time >= 299) stopRef.current();
      const meter = analyser.current;
      if (meter) {
        const samples = new Uint8Array(meter.fftSize);
        meter.getByteTimeDomainData(samples);
        setLevel(Math.max(...samples.map((sample) => Math.abs(sample - 128))) / 128);
      }
    }, 100);
    return () => window.clearInterval(timer);
  }, [phase]);
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );
  useEffect(
    () => () => {
      generation.current += 1;
      cancelled.current = true;
      if (recorder.current?.state !== 'inactive') recorder.current?.stop();
      release();
      active.current(false);
    },
    [],
  );
  useEffect(() => {
    if (disabled && (phase === 'recording' || phase === 'paused')) stopRef.current();
  }, [disabled, phase]);
  async function send() {
    if (!blob.current || disabled || phaseRef.current === 'sending') return;
    transition('sending');
    setProgress(0);
    setError(null);
    try {
      await uploadVoice(conversationId, blob.current, clientId.current, setProgress, replyToId);
      blob.current = null;
      setPreview(null);
      transition('idle');
      onSent();
    } catch (e) {
      transition('preview');
      setError(e instanceof Error ? e.message : 'Upload failed. Please retry.');
    }
  }

  return {
    phase,
    origin,
    start,
    lockRef,
    locked,
    setLocked,
    stop,
    level,
    seconds,
    pause,
    preview,
    send,
    progress,
    error,
  };
}
