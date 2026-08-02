'use client';

import { Alert, Progress, cn } from '@trustlens/ui';
import { imageFileSchema } from '@trustlens/validation';
import { Camera, RefreshCw, Upload } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

export interface ImageCaptureProps {
  id: string;
  label: string;
  hint?: string;
  /**
   * `environment` opens the rear camera, `user` the front one. Passed straight
   * to the file input's capture attribute, which phones honour and desktops
   * ignore - so one component serves both without a device sniff.
   */
  facing?: 'environment' | 'user';
  value: File | null;
  onChange: (file: File | null) => void;
  progress?: number | null;
  disabled?: boolean;
  className?: string;
}

export function ImageCapture({
  id,
  label,
  hint,
  facing = 'environment',
  value,
  onChange,
  progress = null,
  disabled,
  className,
}: ImageCaptureProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Object URLs are a real leak: each one pins the whole image in memory
  // until it is revoked, and a seller retaking a photo five times would pin
  // five full-size bitmaps.
  useEffect(() => {
    if (!value) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(value);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [value]);

  function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;

    // Same schema the backend enforces, so the size and type message a seller
    // sees here is the one they would have got from the server anyway.
    const parsed = imageFileSchema.safeParse(file);
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'That file cannot be used.');
      onChange(null);
      return;
    }
    setError(null);
    onChange(file);
  }

  const busy = progress !== null && progress < 100;

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium">{label}</span>
        {value && !busy && (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={disabled}
            className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            <RefreshCw className="h-3 w-3" aria-hidden="true" />
            Retake
          </button>
        )}
      </div>

      <input
        ref={inputRef}
        id={id}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture={facing}
        className="sr-only"
        disabled={disabled}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        aria-invalid={error ? true : undefined}
        onChange={(event) => handleFiles(event.target.files)}
      />

      {preview ? (
        <div className="overflow-hidden rounded-lg border border-border">
          {/* Deliberately a plain img: this is a local object URL, so
              next/image would only add a proxy the browser cannot use. */}
          <img src={preview} alt={`${label} preview`} className="max-h-64 w-full object-contain" />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
          className={cn(
            'flex w-full flex-col items-center border-border hover:bg-muted focus-visible:ring-ring',
            'justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-10 transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 disabled:opacity-50',
          )}
        >
          {facing === 'user' ? (
            <Camera className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
          ) : (
            <Upload className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
          )}
          <span className="text-sm font-medium">
            {facing === 'user' ? 'Take a selfie' : 'Take a photo or choose a file'}
          </span>
          {hint && (
            <span id={`${id}-hint`} className="text-center text-xs text-muted-foreground">
              {hint}
            </span>
          )}
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

/** Shown above the CNIC step so people take a usable photo the first time. */
export function CaptureTips() {
  return (
    <Alert tone="info" title="For the best chance of first-time approval">
      <ul className="mt-1 list-inside list-disc space-y-0.5">
        <li>Lay the card flat and fill the frame</li>
        <li>Use even light — avoid flash glare across the card</li>
        <li>Make sure all four corners are visible and the text is sharp</li>
        <li>Photograph the real card, not a screen or a photocopy</li>
      </ul>
    </Alert>
  );
}
