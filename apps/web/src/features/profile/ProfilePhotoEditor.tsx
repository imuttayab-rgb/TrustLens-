/** Profilephotoeditor module; defines ProfilePhotoEditor. */
'use client';
import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Alert, Button } from '@trustlens/ui';
import { profileRequest } from './api';
const REASONS: Record<string, string> = {
  CHECK_TIMEOUT:
    'The check took too long. You can submit your photo again; your previous approved photo is unchanged.',
  ONE_CLEAR_FACE_REQUIRED:
    'Use a photo with one clear, unobstructed face. Group photos cannot be approved.',
  MATCH_INCONCLUSIVE:
    'We could not confidently match this photo. Try a recent, well-lit photo without filters.',
  VERIFY_IDENTITY_AGAIN:
    'Your verification evidence changed or expired. Complete ID verification again.',
  REAL_FACE_ENGINE_REQUIRED:
    'A real face-check engine must be enabled on the server. Demo checks cannot approve a profile photo.',
  CHECK_UNAVAILABLE:
    'The photo check could not finish. Please retry; your previous approved photo is unchanged.',
  QUEUE_UNAVAILABLE: 'The check could not start. Please try again.',
};
export function ProfilePhotoEditor({
  enabled,
  status,
  reason,
}: {
  enabled: boolean;
  status?: string;
  reason?: string | null;
}) {
  const qc = useQueryClient();
  const canvas = useRef<HTMLCanvasElement>(null);
  const original = useRef<HTMLImageElement | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [x, setX] = useState(0);
  const [y, setY] = useState(0);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (!url) return;
    const img = new window.Image();
    setLoaded(false);
    img.onload = () => {
      original.current = img;
      setLoaded(true);
    };
    img.onerror = () => {
      setError('This image could not be opened. Choose a JPEG, PNG or WebP photo.');
      setLoaded(false);
    };
    img.src = url;
    return () => {
      img.onload = null;
      img.onerror = null;
      URL.revokeObjectURL(url);
    };
  }, [url]);
  function draw(target: HTMLCanvasElement) {
    const img = original.current;
    if (!img) return;
    const ctx = target.getContext('2d');
    if (!ctx) return;
    const size = target.width;
    const scale = Math.max(size / img.naturalWidth, size / img.naturalHeight) * zoom;
    const w = img.naturalWidth * scale,
      h = img.naturalHeight * scale;
    ctx.clearRect(0, 0, size, size);
    ctx.drawImage(
      img,
      (size - w) / 2 + (x * (w - size)) / 2,
      (size - h) / 2 + (y * (h - size)) / 2,
      w,
      h,
    );
  }
  useEffect(() => {
    if (canvas.current && loaded) draw(canvas.current);
  });
  async function upload() {
    if (!original.current || !consent) return;
    setBusy(true);
    setError(null);
    try {
      const target = document.createElement('canvas');
      target.width = 640;
      target.height = 640;
      draw(target);
      const blob = await new Promise<Blob>((resolve, reject) =>
        target.toBlob(
          (v) => (v ? resolve(v) : reject(new Error('Could not prepare photo.'))),
          'image/jpeg',
          0.9,
        ),
      );
      await profileRequest('/me/profile/photo', {
        method: 'POST',
        headers: { 'Content-Type': 'image/jpeg', 'X-Photo-Consent': 'profile-photo-v1' },
        body: blob,
      });
      setUrl(null);
      setConsent(false);
      await qc.invalidateQueries({ queryKey: ['profile'] });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Photo upload failed.');
    } finally {
      setBusy(false);
    }
  }
  const waiting = status === 'QUEUED' || status === 'PROCESSING';
  return (
    <section className="space-y-3 rounded-xl border border-border bg-card p-4" id="profile-photo">
      <h3 className="font-semibold">Your profile photo</h3>
      <p className="text-xs text-muted-foreground">
        Your own clear face photo is required before ads become public or you send messages. It will
        be compared with your private verification selfie.
      </p>
      {!enabled && <p className="text-sm text-amber-500">Confirm your ID-matched name first.</p>}
      {waiting && (
        <Alert tone="info">
          Your photo is being checked in the background. You can leave this page and return.
        </Alert>
      )}
      {reason && (
        <Alert tone="warning">{REASONS[reason] ?? 'Please retry your profile photo check.'}</Alert>
      )}
      <label className="block text-sm font-medium">
        Choose a photo
        <input
          aria-label="Choose profile photo"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          disabled={!enabled || busy || waiting}
          className="mt-2 block w-full text-xs file:mr-2 file:rounded file:border-0 file:bg-brand/10 file:px-3 file:py-2 file:text-brand"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            if (file.size > 5 * 1024 * 1024) {
              setError('Choose a photo of 5 MB or smaller.');
              return;
            }
            setUrl(URL.createObjectURL(file));
            setZoom(1);
            setX(0);
            setY(0);
            setError(null);
            e.target.value = '';
          }}
        />
      </label>
      {url && (
        <div className="space-y-3">
          <canvas
            ref={canvas}
            width={240}
            height={240}
            aria-label="Profile photo crop preview"
            className="mx-auto w-full max-w-60 rounded-xl border border-border"
          />
          {[
            { label: 'Zoom', value: zoom, set: setZoom, min: 1, max: 3 },
            { label: 'Move horizontally', value: x, set: setX, min: -1, max: 1 },
            { label: 'Move vertically', value: y, set: setY, min: -1, max: 1 },
          ].map((v) => (
            <label key={v.label} className="block text-xs">
              {v.label}
              <input
                type="range"
                min={v.min}
                max={v.max}
                step=".01"
                value={v.value}
                onChange={(e) => v.set(Number(e.target.value))}
                className="mt-1 w-full accent-teal-500"
              />
            </label>
          ))}
          <label className="flex gap-2 text-xs leading-relaxed">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-1"
            />
            I agree to compare this photo with my verification selfie and display the approved photo
            publicly on my profile, ads and chats.
          </label>
          <Button
            className="w-full"
            disabled={!loaded || !consent || busy}
            onClick={() => void upload()}
          >
            {busy ? 'Uploading…' : 'Submit photo for checking'}
          </Button>
        </div>
      )}
      {error && <Alert tone="error">{error}</Alert>}
    </section>
  );
}
