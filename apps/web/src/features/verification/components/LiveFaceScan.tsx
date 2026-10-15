/** Reusable UI rendering and interaction component: LiveFaceScan. */
'use client';

import { Alert, Progress, cn } from '@trustlens/ui';
import { imageFileSchema } from '@trustlens/validation';
import { Camera, RefreshCw } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { FaceLandmarker } from '@mediapipe/tasks-vision';
import {
  advanceChallenge,
  newMotionChallenge,
  observePitch,
  opposite,
  type MotionChallenge,
} from './face-challenge';

interface LiveFaceScanProps {
  value: File | null;
  onChange: (value: File | null) => void;
  progress?: number | null;
  disabled?: boolean;
  className?: string;
}

const MODEL = '/face-scan/face_landmarker.task';
const WASM = '/face-scan/wasm';
const TIMEOUT_MS = 35_000;

/**
 * Client-side pose guidance only. A timed MediaPipe landmark sequence helps
 * ensure the submitted selfie was taken during this camera session. It is not
 * authoritative liveness: the server receives only a still JPEG, so virtual
 * cameras or tampered clients can bypass the challenge. The worker separately
 * compares that JPEG with the CNIC portrait; no face data goes to MediaPipe's
 * servers because both WASM and the landmark model are served locally.
 */
export function LiveFaceScan({
  value,
  onChange,
  progress = null,
  disabled = false,
  className,
}: LiveFaceScanProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const modelRef = useRef<FaceLandmarker | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const disabledRef = useRef(disabled);
  disabledRef.current = disabled;
  const challengeRef = useRef<MotionChallenge>(newMotionChallenge('up'));
  const startedRef = useRef(0);
  const lastVideoTimeRef = useRef(-1);
  const [challenge, setChallenge] = useState<MotionChallenge>(challengeRef.current);
  const [preview, setPreview] = useState<string | null>(null);
  const [active, setActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState('Center your face in the oval.');
  const busy = progress !== null && progress < 100;

  useEffect(() => {
    if (!value) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(value);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [value]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      stop();
      modelRef.current?.close();
      modelRef.current = null;
    };
  }, []);

  useEffect(() => {
    // Consent can change while the camera is running. Close the stream at once;
    // a late permission response is separately rejected in start() below.
    if (disabled && streamRef.current) stop();
  }, [disabled]);

  function stop() {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setActive(false);
  }

  function resetChallenge() {
    // Order is deliberately randomized locally; this is a usability demo,
    // not a cryptographically server-issued proof of fresh human presence.
    const next = newMotionChallenge(crypto.getRandomValues(new Uint8Array(1))[0]! % 2 ? 'up' : 'down');
    challengeRef.current = next;
    setChallenge(next);
    startedRef.current = performance.now();
    lastVideoTimeRef.current = -1;
    setHint('Keep exactly one face visible and hold still to calibrate.');
  }

  function captureNeutralFrame() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !video.videoWidth || !video.videoHeight) return;
    // Keep the JPEG unmirrored. The CSS preview is mirrored for framing, but
    // reversing the stored frame could alter identity evidence and card text.
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      if (!mountedRef.current || disabledRef.current || !blob) return;
      const file = new File([blob], 'live-face.jpg', { type: 'image/jpeg' });
      const parsed = imageFileSchema.safeParse(file);
      if (!parsed.success) {
        setError(parsed.error.issues[0]?.message ?? 'Please retake the face scan.');
        resetChallenge();
        return;
      }
      stop();
      setError(null);
      onChange(file);
    }, 'image/jpeg', 0.86);
  }

  function scanFrame() {
    const video = videoRef.current;
    const model = modelRef.current;
    if (!streamRef.current || !model || !video || !mountedRef.current) return;
    if (performance.now() - startedRef.current > TIMEOUT_MS) {
      stop();
      setError('Scan timed out. Please try again with steady lighting and one face in frame.');
      return;
    }
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.currentTime !== lastVideoTimeRef.current) {
      lastVideoTimeRef.current = video.currentTime;
      try {
        const result = model.detectForVideo(video, performance.now());
        const pitch = observePitch(result);
        const next = advanceChallenge(challengeRef.current, pitch, performance.now());
        challengeRef.current = next;
        setChallenge(next);
        setHint(pitch === null ? 'Keep one face in frame; improve light or move closer.' : 'Hold the position steady.');
        if (next.stage === 'complete') {
          captureNeutralFrame();
          return;
        }
      } catch {
        stop();
        setError('Face tracking stopped. Retry the scan; your previous ID photos are unchanged.');
        return;
      }
    }
    timerRef.current = setTimeout(scanFrame, 140);
  }

  async function start() {
    if (disabled || loading || active) return;
    setError(null);
    onChange(null);
    if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) {
      setError('Live scanning needs a camera and HTTPS (localhost also works).');
      return;
    }
    setLoading(true);
    try {
      // Lazy-load the model only when the seller starts this optional step;
      // the marketplace homepage and the existing verification flow stay light.
      const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision');
      const resolver = await FilesetResolver.forVisionTasks(WASM);
      const model = await FaceLandmarker.createFromOptions(resolver, {
        baseOptions: { modelAssetPath: MODEL, delegate: 'CPU' },
        runningMode: 'VIDEO',
        numFaces: 2,
        outputFacialTransformationMatrixes: true,
      });
      if (!mountedRef.current || disabledRef.current) {
        model.close();
        return;
      }
      modelRef.current?.close();
      modelRef.current = model;
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
      });
      if (!mountedRef.current || disabledRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      // Video stays mounted even before 'active', so the first camera stream
      // is attached before play() (avoids the old conditional-rendering race).
      const video = videoRef.current;
      if (!video) throw new Error('Camera preview unavailable');
      video.srcObject = stream;
      await video.play();
      resetChallenge();
      setActive(true);
      timerRef.current = setTimeout(scanFrame, 140);
    } catch {
      stop();
      setError('Camera or face model unavailable. Check camera permission and retry.');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }

  const prompt =
    challenge.stage === 'center'
      ? 'Look straight at the camera and hold still.'
      : challenge.stage === 'return'
        ? 'Look straight ahead again and hold still.'
        : challenge.stage === 'first'
          ? `Look ${challenge.first} and hold still.`
          : challenge.stage === 'second'
            ? `Look ${opposite(challenge.first)} and hold still.`
            : 'Face scan captured.';

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">Live face scan</span>
        {value && !disabled && (
          <button type="button" className="inline-flex items-center gap-1 text-sm underline" onClick={() => void start()}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" /> Retake
          </button>
        )}
      </div>
      <Alert tone="info" title="Look up, then down (order may change)">
        Keep your face alone in the camera frame. We use a neutral frame from this scan for comparison with the portrait on your submitted ID. This motion check does not prove identity or rule out sophisticated replays.
      </Alert>
      <canvas ref={canvasRef} className="hidden" aria-hidden="true" />
      {preview && !active && (
        <img src={preview} alt="Your captured face" className="max-h-72 w-full rounded-lg border border-border object-contain" />
      )}
      <div className={cn('relative overflow-hidden rounded-xl border border-border bg-black', preview && !active && 'hidden')}>
        {/* This video stays mounted on retakes so start() always finds its ref. */}
        <video ref={videoRef} muted playsInline className="aspect-[4/3] w-full scale-x-[-1] object-cover" />
        <div className="pointer-events-none absolute inset-8 rounded-[45%] border-2 border-dashed border-white/80" aria-hidden="true" />
        {active && (
          <div className="absolute inset-x-3 bottom-3 rounded-lg bg-black/85 px-4 py-3 text-center text-white" aria-live="polite">
            <p className="font-semibold">{prompt}</p>
            <p className="text-xs">{hint} · {Math.min(['center', 'first', 'second', 'return'].indexOf(challenge.stage) + 1, 4)}/4</p>
          </div>
        )}
      </div>
      {!active && !value && (
        <button type="button" disabled={loading || disabled} onClick={() => void start()}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-border px-4 py-3 font-medium hover:bg-muted disabled:opacity-50">
          <Camera className="h-5 w-5" aria-hidden="true" />
          {loading ? 'Loading local face tracker…' : 'Start live face scan'}
        </button>
      )}
      {active && <button type="button" className="text-sm underline" onClick={stop}>Cancel scan</button>}
      {busy && <Progress value={progress} label="Uploading live face image" />}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
