/** Reusable UI rendering and interaction component: HoldIdFaceScan. */
'use client';

import { Alert, Progress, cn } from '@trustlens/ui';
import { imageFileSchema } from '@trustlens/validation';
import { Camera, RefreshCw } from 'lucide-react';
import * as React from 'react';
import { useEffect, useRef, useState } from 'react';
import type { FaceLandmarker } from '@mediapipe/tasks-vision';
import { advanceChallenge, newMotionChallenge, opposite, type MotionChallenge } from './face-challenge';
import { observeHolderPitch } from './hold-face-challenge';

interface HoldIdFaceScanProps {
  value: File | null;
  onChange: (value: File | null) => void;
  progress?: number | null;
  disabled?: boolean;
}

const MODEL = '/face-scan/face_landmarker.task';
const WASM = '/face-scan/wasm';

/**
 * Fourth step: capture the applicant WITH the front of their physical ID.
 * Camera movement is guidance, not server-verified PAD. A single final JPEG is
 * stored privately and must be reviewed by a human alongside front/back/selfie.
 */
export function HoldIdFaceScan({ value, onChange, progress = null, disabled = false }: HoldIdFaceScanProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const modelRef = useRef<FaceLandmarker | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const disabledRef = useRef(disabled);
  disabledRef.current = disabled;
  const challengeRef = useRef<MotionChallenge>(newMotionChallenge('up'));
  const lastVideoTimeRef = useRef(-1);
  const startedRef = useRef(0);
  const [challenge, setChallenge] = useState(challengeRef.current);
  const [active, setActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const hintId = React.useId();

  useEffect(() => {
    if (!value) { setPreview(null); return; }
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
  useEffect(() => { if (disabled && streamRef.current) stop(); }, [disabled]);

  function stop() {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    if (mountedRef.current) setActive(false);
  }

  function capture() {
    const video = videoRef.current;
    if (!video?.videoWidth || !video.videoHeight) return;
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, 1600 / video.videoWidth);
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    const ctx = canvas.getContext('2d');
    if (!ctx) { stop(); setError('Could not save camera frame. Retry.'); return; }
    // CSS mirrors only the preview. Preserve original pixels/card text for the
    // worker's front-card feature match and reviewer inspection.
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    stop();
    canvas.toBlob((blob) => {
      if (!mountedRef.current || disabledRef.current || !blob) return;
      const file = new File([blob], 'hold-id-beside-face.jpg', { type: 'image/jpeg' });
      const parsed = imageFileSchema.safeParse(file);
      if (!parsed.success) { setError(parsed.error.issues[0]?.message ?? 'Retake this frame.'); return; }
      onChange(file);
    }, 'image/jpeg', 0.9);
  }

  function scanFrame() {
    const video = videoRef.current;
    const model = modelRef.current;
    if (!streamRef.current || !model || !video || !mountedRef.current) return;
    if (performance.now() - startedRef.current > 50_000) {
      stop(); setError('Scan timed out. Improve lighting, then try again with card and face visible.'); return;
    }
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.currentTime !== lastVideoTimeRef.current) {
      lastVideoTimeRef.current = video.currentTime;
      try {
        const result = model.detectForVideo(video, performance.now());
        // The card portrait can register as a second, SMALL face. Guide the
        // applicant (largest face); only backend/reviewer checks the card.
        const pitch = observeHolderPitch(result);
        const next = advanceChallenge(challengeRef.current, pitch, performance.now());
        challengeRef.current = next;
        setChallenge(next);
        if (next.stage === 'complete') { capture(); return; }
      } catch {
        stop(); setError('Face tracking stopped. Please retry.'); return;
      }
    }
    timerRef.current = setTimeout(scanFrame, 140);
  }

  async function start() {
    if (disabled || loading || active) return;
    setError(null);
    onChange(null);
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setError('Camera and HTTPS are required. localhost works on this laptop.'); return;
    }
    setLoading(true);
    try {
      const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision');
      const resolver = await FilesetResolver.forVisionTasks(WASM);
      const model = await FaceLandmarker.createFromOptions(resolver, {
        baseOptions: { modelAssetPath: MODEL, delegate: 'CPU' },
        runningMode: 'VIDEO', numFaces: 2, outputFacialTransformationMatrixes: true,
      });
      if (!mountedRef.current || disabledRef.current) { model.close(); return; }
      modelRef.current?.close(); modelRef.current = model;
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: 'user' }, width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      if (!mountedRef.current || disabledRef.current) {
        stream.getTracks().forEach((track) => track.stop()); return;
      }
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) throw new Error('Camera preview unavailable');
      video.srcObject = stream;
      await video.play();
      const first = crypto.getRandomValues(new Uint8Array(1))[0]! % 2 ? 'up' : 'down';
      challengeRef.current = newMotionChallenge(first);
      setChallenge(challengeRef.current);
      startedRef.current = performance.now(); lastVideoTimeRef.current = -1;
      setActive(true);
      timerRef.current = setTimeout(scanFrame, 140);
    } catch {
      stop(); setError('Camera or local face tracker unavailable. Check permission and retry.');
    } finally { if (mountedRef.current) setLoading(false); }
  }

  const prompt = challenge.stage === 'center' ? 'Hold the FRONT of your card beside your face and look straight.'
    : challenge.stage === 'first' ? `Keep the card beside your face; look ${challenge.first} and hold.`
      : challenge.stage === 'second' ? `Keep the card visible; look ${opposite(challenge.first)} and hold.`
        : challenge.stage === 'return' ? 'Look straight ahead; keep card and face fully visible.'
          : 'Holding-card image captured for review.';

  return <div className="space-y-3">
    <p className="text-sm font-medium">ID beside face — final step</p>
    <div id={hintId}><Alert tone="info">
      Hold the FRONT of your physical ID beside (not over) your face, with the card portrait toward the camera. Follow the prompts while keeping both visible. One final frame is uploaded privately for manual review. This does not prove NADRA authenticity or certified liveness.
    </Alert></div>
    {preview && !active && <img src={preview} alt="Captured applicant holding an ID beside their face" className="max-h-72 w-full rounded-lg border object-contain" />}
    <div className={cn('relative overflow-hidden rounded-xl border bg-black', preview && !active && 'hidden')}>
      <video ref={videoRef} muted playsInline className="aspect-[4/3] w-full scale-x-[-1] object-contain" />
      {active && <div className="absolute inset-x-3 bottom-3 rounded-lg bg-black/85 px-4 py-3 text-center text-white" aria-live="polite">{prompt}</div>}
    </div>
    {!active && !value && <button type="button" disabled={disabled || loading} aria-describedby={hintId} onClick={() => void start()} className="flex w-full items-center justify-center gap-2 rounded-lg border px-4 py-3 font-medium disabled:opacity-50"><Camera className="h-5 w-5" aria-hidden="true" />{loading ? 'Loading local camera tracker…' : 'Scan with ID beside face'}</button>}
    {value && !disabled && <button type="button" onClick={() => void start()} className="inline-flex items-center gap-1 text-sm underline"><RefreshCw className="h-4 w-4" aria-hidden="true" /> Retake</button>}
    {active && <button type="button" className="text-sm underline" onClick={stop}>Cancel scan</button>}
    {progress !== null && progress < 100 && <Progress value={progress} label="Uploading private holding-card evidence" />}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
  </div>;
}
