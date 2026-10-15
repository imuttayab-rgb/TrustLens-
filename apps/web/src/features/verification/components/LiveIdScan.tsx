/** Reusable UI rendering and interaction component: LiveIdScan. */
'use client';

import { Alert, Progress, cn } from '@trustlens/ui';
import { imageFileSchema } from '@trustlens/validation';
import { Camera, RefreshCw } from 'lucide-react';
import * as React from 'react';
import { useEffect, useRef, useState } from 'react';
import {
  advanceDocumentChallenge,
  analyzeDocumentFrame,
  newDocumentChallenge,
  oppositeDirection,
  type DocumentChallenge,
  type Side,
} from './id-scan-challenge';

interface LiveIdScanProps {
  side: Side;
  value: File | null;
  onChange: (value: File | null) => void;
  progress?: number | null;
  disabled?: boolean;
  className?: string;
}

const TIMEOUT_MS = 45_000;

/**
 * An opt-in, browser-only live document CAPTURE helper; not a document-liveness
 * certification. The upload is still the existing JPEG + signed POST pipeline.
 * A modified browser, virtual camera, video of a card, or a stolen real card can
 * bypass this presentation check. The backend must continue OCR/face comparison
 * and ambiguous evidence must remain eligible for human review.
 */
export function LiveIdScan({
  side,
  value,
  onChange,
  progress = null,
  disabled = false,
  className,
}: LiveIdScanProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const analysisCanvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const disabledRef = useRef(disabled);
  disabledRef.current = disabled;
  const startedRef = useRef(0);
  const lastVideoTimeRef = useRef(-1);
  const challengeRef = useRef<DocumentChallenge>(newDocumentChallenge(side, 'left'));
  const [stage, setStage] = useState<DocumentChallenge['stage']>('center');
  const [active, setActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [hint, setHint] = useState('Fill the guide with the card and hold it steady.');
  const [error, setError] = useState<string | null>(null);
  const instructionsId = React.useId();
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
    };
  }, []);

  useEffect(() => {
    // Consent withdrawal or an in-progress upload must stop a live camera.
    if (disabled && streamRef.current) stop();
  }, [disabled]);

  function stop() {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    if (mountedRef.current) setActive(false);
  }

  function captureFrame() {
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) return;
    // Retain the full unmirrored sensor frame: OCR needs all four card edges,
    // and changing pixels to cosmetically straighten them can lose evidence.
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, 1600 / video.videoWidth);
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      stop();
      setError('Cannot capture the card. Please try this camera again.');
      return;
    }
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    stop();
    canvas.toBlob((blob) => {
      if (!mountedRef.current || disabledRef.current) return;
      if (!blob) {
        setError('Camera capture failed. Please retry.');
        return;
      }
      const file = new File([blob], `live-cnic-${side}.jpg`, { type: 'image/jpeg' });
      const result = imageFileSchema.safeParse(file);
      if (!result.success) {
        setError(result.error.issues[0]?.message ?? 'Card image is too large. Please retry.');
        return;
      }
      setError(null);
      onChange(file);
    }, 'image/jpeg', 0.90);
  }

  function scanFrame() {
    const video = videoRef.current;
    const canvas = analysisCanvasRef.current;
    if (!mountedRef.current || !streamRef.current || !video || !canvas) return;
    if (performance.now() - startedRef.current > TIMEOUT_MS) {
      stop();
      setError('Scan timed out. Improve the light and try again with one card in the guide.');
      return;
    }
    if (
      video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
      video.currentTime !== lastVideoTimeRef.current
    ) {
      lastVideoTimeRef.current = video.currentTime;
      try {
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        if (!ctx) throw new Error('2D canvas unavailable');
        // Only a small image grid is analyzed on this device at ~5 fps. No
        // video is uploaded, recorded to disk, or sent to a third party.
        canvas.width = 320;
        canvas.height = 240;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const quality = analyzeDocumentFrame(pixels.data, canvas.width, canvas.height);
        const next = advanceDocumentChallenge(challengeRef.current, quality, performance.now());
        challengeRef.current = next;
        setStage(next.stage);
        setHint(quality.okay ? 'Keep the card fully inside the guide.' : quality.reason);
        if (next.stage === 'complete') {
          captureFrame();
          return;
        }
      } catch {
        stop();
        setError('Camera frame processing failed. Please retry the scan.');
        return;
      }
    }
    timerRef.current = setTimeout(scanFrame, 180);
  }

  async function start() {
    if (disabled || loading || active) return;
    setError(null);
    // Retakes clear the old frame BEFORE opening the camera; no saved gallery
    // file can silently be relabeled as the output of this live capture.
    onChange(null);
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setError('A webcam and HTTPS are required. localhost also works on this laptop.');
      return;
    }
    setLoading(true);
    try {
      // `ideal`, not `exact`: built-in laptop webcams are commonly the only
      // camera and must remain usable when no rear-facing device exists.
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      if (!mountedRef.current || disabledRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) throw new Error('Camera preview unavailable');
      video.srcObject = stream;
      await video.play();
      // The direction changes on each attempt; this is NOT a server-signed
      // challenge or proof that the ID really belongs to this seller.
      const direction = crypto.getRandomValues(new Uint8Array(1))[0]! % 2 ? 'left' : 'right';
      challengeRef.current = newDocumentChallenge(side, direction);
      lastVideoTimeRef.current = -1;
      startedRef.current = performance.now();
      setStage('center');
      setActive(true);
      timerRef.current = setTimeout(scanFrame, 180);
    } catch {
      stop();
      setError('Webcam unavailable. Check camera permission and try again; no gallery upload is accepted.');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }

  const first = challengeRef.current.first;
  const prompt = stage === 'center' ? 'Center the card and hold still.'
    : stage === 'first' ? `Move the card ${first} inside the guide; hold still.`
    : stage === 'second' ? `Now move the card ${oppositeDirection(first)}; hold still.`
    : stage === 'return' ? 'Return card to the center; hold still for capture.'
    : 'Card captured.';

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">CNIC — {side}</span>
        {value && !disabled && (
          <button type="button" className="inline-flex items-center gap-1 text-sm underline" onClick={() => void start()}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" /> Retake
          </button>
        )}
      </div>
      <div id={instructionsId}>
        <Alert tone="info">
          Show the {side} of your physical card to the webcam. Follow the random left/right movement and hold steady; a clear frame is captured automatically. No gallery selection is available.
        </Alert>
      </div>
      {preview && !active && (
        <img src={preview} alt={`Captured CNIC ${side}`} className="max-h-72 w-full rounded-lg border border-border object-contain" />
      )}
      {/* Always mount the video, including on retake. Otherwise a conditional
          render can leave videoRef null between getUserMedia() and play(). */}
      <div className={cn('relative overflow-hidden rounded-xl border border-border bg-black', preview && !active && 'hidden')}>
        <video ref={videoRef} muted playsInline className="aspect-[4/3] w-full object-contain" />
        <div className="pointer-events-none absolute bottom-[20%] left-[12.5%] right-[12.5%] top-[20%] rounded-xl border-2 border-dashed border-white/90" aria-hidden="true" />
        {active && (
          <div className="absolute inset-x-3 bottom-3 rounded-lg bg-black/85 px-4 py-3 text-center text-white" aria-live="polite">
            <p className="font-semibold">{prompt}</p>
            <p className="text-xs">{hint} · {['center', 'first', 'second', 'return'].indexOf(stage) + 1}/4</p>
          </div>
        )}
      </div>
      <canvas ref={analysisCanvasRef} className="hidden" aria-hidden="true" />
      {!active && !value && (
        <button type="button" disabled={loading || disabled} aria-describedby={instructionsId} onClick={() => void start()}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-border px-4 py-3 font-medium hover:bg-muted disabled:opacity-50">
          <Camera className="h-5 w-5" aria-hidden="true" />
          {loading ? 'Opening webcam…' : `Start live ${side} scan`}
        </button>
      )}
      {active && <button type="button" className="text-sm underline" onClick={stop}>Cancel scan</button>}
      {disabled && !busy && !value && <p className="text-sm text-muted-foreground">Give consent before starting the camera.</p>}
      {busy && <Progress value={progress} label={`Uploading CNIC ${side}`} />}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
