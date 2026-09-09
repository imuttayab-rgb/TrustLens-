'use client';

import { Alert, Progress, cn } from '@trustlens/ui';
import { imageFileSchema } from '@trustlens/validation';
import { Camera, RefreshCw, Upload } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

export interface SelfieCaptureProps {
  id: string;
  label: string;
  value: File | null;
  onChange: (file: File | null) => void;
  progress?: number | null;
  disabled?: boolean;
  className?: string;
}

/**
 * A live camera stream, not a file picker.
 *
 * A gallery photo proves nothing about who is sitting behind the screen right
 * now - it can be any picture of anyone. Forcing the front camera and asking
 * the seller to hold their CNIC next to their face closes that gap: the
 * shot has to be taken live, at this moment, with the same card the seller
 * uploaded in the previous step visible in frame. It is not full liveness
 * detection (no blink/pose challenge yet - see docs/19), but it is a real
 * step up from "pick any file", which is what this replaces.
 *
 * Falls back to the old file-input behaviour when the camera is unavailable
 * or the seller denies permission, so the flow still completes on a desktop
 * with no webcam rather than dead-ending.
 */
export function SelfieCapture({
  id,
  label,
  value,
  onChange,
  progress = null,
  disabled,
  className,
}: SelfieCaptureProps) {
  const busy = progress !== null && progress < 100;
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fallbackInputRef = useRef<HTMLInputElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [useFallback, setUseFallback] = useState(false);

  useEffect(() => {
    if (!value) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(value);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [value]);

  function stopStream() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setStreaming(false);
  }

  useEffect(() => stopStream, []);

  async function startStream() {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setUseFallback(true);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user' },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStreaming(true);
    } catch {
      // Denied, no camera, or an insecure (non-HTTPS) context - all the same
      // outcome from the seller's side: fall back rather than dead-end.
      setUseFallback(true);
    }
  }

  function capture() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    // Mirror the capture to match the mirrored preview the seller was
    // framing themselves in - otherwise the saved photo is flipped relative
    // to what they saw and CNIC text held up to the camera reads backwards.
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const file = new File([blob], `${id}.jpg`, { type: 'image/jpeg' });
        const parsed = imageFileSchema.safeParse(file);
        if (!parsed.success) {
          setError(parsed.error.issues[0]?.message ?? 'That photo could not be used.');
          return;
        }
        setError(null);
        onChange(file);
        stopStream();
      },
      'image/jpeg',
      0.92,
    );
  }

  function retake() {
    onChange(null);
    setError(null);
    void startStream();
  }

  function handleFallbackFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    const parsed = imageFileSchema.safeParse(file);
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'That file cannot be used.');
      onChange(null);
      return;
    }
    setError(null);
    onChange(file);
  }

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium">{label}</span>
        {value && !busy && (
          <button
            type="button"
            onClick={useFallback ? () => fallbackInputRef.current?.click() : retake}
            disabled={disabled}
            className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            <RefreshCw className="h-3 w-3" aria-hidden="true" />
            Retake
          </button>
        )}
      </div>

      {!value && !useFallback && (
        <Alert tone="info" title="Hold your CNIC next to your face">
          Keep both your face and the card clearly visible in the frame before you capture.
        </Alert>
      )}

      <canvas ref={canvasRef} className="hidden" />

      {preview ? (
        <div className="overflow-hidden rounded-lg border border-border">
          {/* Deliberately a plain img: this is a local object URL, so
              next/image would only add a proxy the browser cannot use. */}
          <img src={preview} alt={`${label} preview`} className="max-h-64 w-full object-contain" />
        </div>
      ) : useFallback ? (
        <>
          <input
            ref={fallbackInputRef}
            id={id}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="user"
            className="sr-only"
            disabled={disabled}
            aria-describedby={error ? `${id}-error` : undefined}
            aria-invalid={error ? true : undefined}
            onChange={(event) => handleFallbackFiles(event.target.files)}
          />
          <button
            type="button"
            onClick={() => fallbackInputRef.current?.click()}
            disabled={disabled}
            className="flex w-full flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border px-4 py-10 text-muted-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
          >
            <Upload className="h-6 w-6" aria-hidden="true" />
            <span className="text-sm font-medium">Take a selfie</span>
            <span className="text-center text-xs text-muted-foreground">
              We could not access your camera directly - your phone or browser will open its own
              camera for this.
            </span>
          </button>
        </>
      ) : streaming ? (
        <div className="relative overflow-hidden rounded-lg border border-border bg-black">
          <video
            ref={videoRef}
            playsInline
            muted
            className="aspect-[3/4] w-full scale-x-[-1] object-cover"
          />
          {/* A rough framing guide, not a face-detection box - it costs
              nothing and still tells the seller where to hold the card. */}
          <div className="pointer-events-none absolute inset-6 rounded-2xl border-2 border-dashed border-white/70" />
          <button
            type="button"
            onClick={capture}
            disabled={disabled}
            className="absolute inset-x-0 bottom-4 mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-white shadow-lg ring-4 ring-white/30 transition-transform active:scale-95 disabled:opacity-50"
            aria-label="Capture selfie"
          >
            <span className="h-11 w-11 rounded-full bg-brand" />
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => void startStream()}
          disabled={disabled}
          className="flex w-full flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border px-4 py-10 text-muted-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        >
          <Camera className="h-6 w-6" aria-hidden="true" />
          <span className="text-sm font-medium">Open camera</span>
        </button>
      )}

      {busy && <Progress value={progress} label={`Uploading ${label}`} />}

      {error && (
        <p id={`${id}-error`} role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
