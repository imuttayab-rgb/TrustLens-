/** Reusable UI rendering and interaction component: PostAdMediaStep. */
'use client';
import { useManageListingPhotos } from '../hooks/use-listings';

import { uploadFile } from '@/lib/upload';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Spinner } from '@trustlens/ui';
import { Camera, CheckCircle2, CircleDot, Film, ImagePlus, Square, Upload } from 'lucide-react';
import Image from 'next/image';
import { useEffect, useRef, useState } from 'react';
import { useAddListingImage, useListingImages } from '../hooks/use-listings';
import {
  checkVideo,
  formatSeconds,
  MAX_PHOTOS,
  MAX_VIDEO_SECONDS,
  MIN_VIDEO_SECONDS,
} from './post-ad-helpers';

/** What the wizard knows about the attached product video. */
export interface AttachedVideo {
  fileId: string;
  /** Local blob URL, only for a clip chosen or recorded in this session. */
  previewUrl: string | null;
  durationSeconds: number | null;
  sizeBytes: number | null;
  type: string | null;
}

/** Read a clip's length in the browser (null when the browser can't tell). */
function readVideoDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const el = document.createElement('video');
    let settled = false;
    const done = (value: number | null) => {
      if (settled) return;
      settled = true;
      URL.revokeObjectURL(url);
      resolve(value);
    };
    el.preload = 'metadata';
    el.muted = true;
    el.onloadedmetadata = () => done(Number.isFinite(el.duration) ? el.duration : null);
    el.onerror = () => done(null);
    window.setTimeout(() => done(null), 8000);
    el.src = url;
  });
}

/**
 * Recorder format. WebM first (Chrome/Edge/Firefox/Android), MP4 for Safari
 * and iPhone. Both are accepted by the backend; .mov is not, because Chrome
 * cannot play an iPhone HEVC .mov for buyers.
 */
function pickRecorderType(): string | null {
  if (typeof MediaRecorder === 'undefined') return null;
  const options = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm', 'video/mp4'];
  return options.find((type) => MediaRecorder.isTypeSupported(type)) ?? null;
}

export function PostAdMediaStep({
  listingId,
  video,
  onVideoReady,
  optional = false,
}: {
  optional?: boolean;
  listingId: string;
  video: AttachedVideo | null;
  /** Uploaded clip -> the wizard saves its file id on the listing. */
  onVideoReady: (video: AttachedVideo) => Promise<void>;
}) {
  const { data: images = [], isPending } = useListingImages(listingId);
  const addImage = useAddListingImage(listingId);
  const manage = useManageListingPhotos(listingId);
  async function editPhoto(action: { removeId: string } | { order: string[] }) {
    try {
      setPhotoError(null);
      await manage.mutateAsync(action);
    } catch (e) {
      setPhotoError(toApiError(e).message || 'Could not update photos.');
    }
  }
  const photoInput = useRef<HTMLInputElement>(null);
  const videoInput = useRef<HTMLInputElement>(null);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);
  const [videoBusy, setVideoBusy] = useState<number | null>(null); // upload progress %
  const [videoError, setVideoError] = useState<string | null>(null);

  // ── Live recording state ────────────────────────────────────────────
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const liveVideo = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<number | null>(null);
  const startedAt = useRef(0);

  function stopStream() {
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }
  // Never leave the camera light on when the seller leaves the step.
  useEffect(() => stopStream, []);

  // The preview <video> only mounts once `recording` is true, so attach the
  // camera stream after that render rather than inside startRecording.
  useEffect(() => {
    if (recording && liveVideo.current && streamRef.current) {
      liveVideo.current.srcObject = streamRef.current;
      void liveVideo.current.play().catch(() => undefined);
    }
  }, [recording]);

  async function handlePhotos(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = '';
    if (files.length === 0) return;
    if (images.length + files.length > MAX_PHOTOS) {
      setPhotoError(`An ad can have at most ${MAX_PHOTOS} photos.`);
      return;
    }
    setPhotoBusy(true);
    setPhotoError(null);
    setDuplicateWarning(null);
    try {
      for (const file of files) {
        const fileId = await uploadFile('LISTING_IMAGE', file);
        const result = await addImage.mutateAsync(fileId);
        if (result.isDuplicate) {
          setDuplicateWarning(
            'One photo looks like a near-duplicate of another. Different angles help buyers more.',
          );
        }
      }
    } catch (err) {
      setPhotoError(
        (toApiError(err).message || 'Photo upload failed.') +
          ' Photos already accepted are saved; select only the remaining photos to retry.',
      );
    } finally {
      setPhotoBusy(false);
    }
  }

  async function uploadClip(file: File, durationSeconds: number | null) {
    const problem = checkVideo({ type: file.type, sizeBytes: file.size, durationSeconds });
    if (problem) {
      setVideoError(problem);
      return;
    }
    setVideoError(null);
    setVideoBusy(5);
    try {
      const fileId = await uploadFile('LISTING_VIDEO', file, { onProgress: setVideoBusy });
      await onVideoReady({
        fileId,
        previewUrl: URL.createObjectURL(file),
        durationSeconds,
        sizeBytes: file.size,
        type: file.type,
      });
    } catch (err) {
      setVideoError(toApiError(err).message || 'Video upload failed.');
    } finally {
      setVideoBusy(null);
    }
  }

  async function handleVideoFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    await uploadClip(file, await readVideoDuration(file));
  }

  async function startRecording() {
    setVideoError(null);
    const mimeType = pickRecorderType();
    if (!mimeType || !navigator.mediaDevices?.getUserMedia) {
      setVideoError('This browser cannot record video. Upload an MP4 or WebM file instead.');
      return;
    }
    try {
      // Video only: the site's Permissions-Policy blocks the microphone, and
      // a product clip needs no audio.
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      streamRef.current = stream;
      const chunks: Blob[] = [];
      const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 2_500_000 });
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      recorder.onstop = () => {
        const seconds = (Date.now() - startedAt.current) / 1000;
        stopStream();
        setRecording(false);
        const baseType = mimeType.split(';')[0] ?? 'video/webm';
        const extension = baseType === 'video/mp4' ? 'mp4' : 'webm';
        const file = new File(
          [new Blob(chunks, { type: baseType })],
          `listing-video.${extension}`,
          {
            type: baseType,
          },
        );
        // MediaRecorder WebM often reports no duration, so the timer is the
        // reliable length for a recorded clip.
        void uploadClip(file, seconds);
      };
      recorderRef.current = recorder;
      startedAt.current = Date.now();
      setElapsed(0);
      recorder.start(1000);
      setRecording(true);
      timerRef.current = window.setInterval(() => {
        const seconds = (Date.now() - startedAt.current) / 1000;
        setElapsed(seconds);
        if (seconds >= MAX_VIDEO_SECONDS && recorderRef.current?.state === 'recording') {
          recorderRef.current.stop();
        }
      }, 250);
    } catch {
      stopStream();
      setRecording(false);
      setVideoError(
        'Camera blocked or unavailable. Allow camera access (HTTPS or localhost is required), or upload a file instead.',
      );
    }
  }

  function stopRecording() {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
  }

  const canStop = elapsed >= MIN_VIDEO_SECONDS;
  const videoChecks = video
    ? [
        {
          label: 'MP4 or WebM',
          ok: video.type === null || /video\/(mp4|webm)/.test(video.type),
        },
        {
          label:
            video.durationSeconds !== null
              ? `Length ${formatSeconds(video.durationSeconds)} (10-60 s)`
              : 'Length 10-60 s',
          ok: true,
        },
        {
          label:
            video.sizeBytes !== null
              ? `Size ${(video.sizeBytes / (1024 * 1024)).toFixed(1)} MB (max 50 MB)`
              : 'Size up to 50 MB',
          ok: true,
        },
      ]
    : [];

  return (
    <div className="space-y-5">
      {/* ── Photos ─────────────────────────────────────────────────── */}
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-base font-semibold">
            Photos {!optional && <span className="text-destructive">*</span>}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              {optional ? 'Optional, up to' : 'At least 1, up to'} {MAX_PHOTOS}. The first photo is
              your main photo.
            </span>
          </h2>
          <span className="text-xs font-medium text-muted-foreground">
            {images.length} of {MAX_PHOTOS} photos
          </span>
        </div>
        {photoError && (
          <Alert tone="error" title="Photo upload failed" className="mt-3">
            {photoError}
          </Alert>
        )}
        <p className="text-text-muted text-xs">
          Use your own product photos. Copies from another account are checked before attachment.
        </p>
        {duplicateWarning && (
          <Alert tone="warning" title="Similar photo" className="mt-3">
            {duplicateWarning}
          </Alert>
        )}
        {isPending ? (
          <div className="mt-4">
            <Spinner label="Loading photos..." />
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {images.map((img) => (
              <div
                key={img.imageId}
                className="relative aspect-square overflow-hidden rounded-lg border border-border bg-muted"
              >
                {img.thumbnailUrl || img.url ? (
                  <Image
                    src={img.thumbnailUrl ?? img.url ?? ''}
                    alt="Listing photo"
                    fill
                    className="object-cover"
                    unoptimized
                  />
                ) : (
                  <Camera className="m-auto h-8 w-8 opacity-20" aria-hidden="true" />
                )}
                <div className="absolute inset-x-1 top-1 flex flex-wrap gap-1">
                  <button
                    type="button"
                    disabled={photoBusy || manage.isPending || img.isPrimary}
                    onClick={() =>
                      void editPhoto({
                        order: [
                          img.imageId,
                          ...images.filter((x) => x.imageId !== img.imageId).map((x) => x.imageId),
                        ],
                      })
                    }
                    className="rounded-md border border-border bg-background/95 px-2 py-1 text-[11px] text-foreground disabled:opacity-50"
                  >
                    Make main
                  </button>
                  <button
                    type="button"
                    disabled={photoBusy || manage.isPending}
                    onClick={() => {
                      if (
                        window.confirm(
                          'Remove this photo from the ad? The ad will need another safety check.',
                        )
                      )
                        void editPhoto({ removeId: img.imageId });
                    }}
                    className="rounded-md border border-border bg-background/95 px-2 py-1 text-[11px] text-foreground"
                  >
                    Remove
                  </button>
                </div>
                {img.isPrimary && (
                  <span className="absolute bottom-2 left-2 rounded-md bg-brand px-2 py-0.5 text-[11px] font-semibold text-white shadow">
                    Main photo
                  </span>
                )}
              </div>
            ))}
            {images.length < MAX_PHOTOS && (
              <button
                type="button"
                onClick={() => photoInput.current?.click()}
                disabled={photoBusy || manage.isPending}
                className="flex aspect-square flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-brand/40 text-brand transition-colors hover:border-brand hover:bg-brand/5 disabled:opacity-60"
              >
                {photoBusy ? (
                  <span className="flex flex-col items-center gap-2">
                    <Spinner />
                    <span className="text-xs">Checking photo…</span>
                  </span>
                ) : (
                  <>
                    <ImagePlus className="h-7 w-7" aria-hidden="true" />
                    <span className="text-sm font-medium">Add photo</span>
                  </>
                )}
              </button>
            )}
          </div>
        )}
        <input
          ref={photoInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          className="hidden"
          onChange={(e) => void handlePhotos(e)}
        />
      </section>

      {/* ── Video ──────────────────────────────────────────────────── */}
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-base font-semibold">
            {optional ? 'Supporting video (optional)' : 'Product video'}{' '}
            {!optional && <span className="text-destructive">*</span>}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              {optional
                ? 'Only upload relevant footage you own. '
                : 'Show the real item from all sides. '}
              10-60 seconds, MP4 or WebM, up to 50 MB.
            </span>
          </h2>
          {video && (
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> Video attached
            </span>
          )}
        </div>

        {videoError && (
          <Alert tone="error" title="Video not accepted" className="mt-3">
            {videoError}
          </Alert>
        )}

        <div className="mt-4 grid gap-4 md:grid-cols-[1fr_220px]">
          <div className="relative aspect-video overflow-hidden rounded-lg border border-border bg-slate-900">
            {recording ? (
              <>
                {}
                <video
                  ref={liveVideo}
                  muted
                  playsInline
                  autoPlay
                  className="h-full w-full object-cover"
                />
                <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-red-600 px-2.5 py-1 text-xs font-semibold text-white">
                  <CircleDot className="h-3.5 w-3.5 animate-pulse" aria-hidden="true" />
                  REC {formatSeconds(elapsed)} / {formatSeconds(MAX_VIDEO_SECONDS)}
                </span>
                <span className="absolute bottom-3 left-3 right-3 rounded-md bg-black/60 px-3 py-1.5 text-center text-xs text-white">
                  {canStop
                    ? 'Good. Stop whenever you have shown every side.'
                    : `Keep going: at least ${MIN_VIDEO_SECONDS} seconds. Turn the item slowly.`}
                </span>
              </>
            ) : video?.previewUrl ? (
              <video
                src={video.previewUrl}
                controls
                muted
                playsInline
                className="h-full w-full object-contain"
              />
            ) : video ? (
              <div className="flex h-full flex-col items-center justify-center gap-2 text-white/80">
                <Film className="h-10 w-10" aria-hidden="true" />
                <span className="text-sm">Video uploaded earlier and saved on this ad.</span>
              </div>
            ) : videoBusy !== null ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-white">
                <Spinner />
                <span className="text-sm">Uploading video... {Math.round(videoBusy)}%</span>
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center text-white/80">
                <Film className="h-10 w-10" aria-hidden="true" />
                <span className="text-sm">
                  No video yet. Buyers trust ads that show the real item working.
                </span>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2">
            {recording ? (
              <Button
                type="button"
                variant="destructive"
                onClick={stopRecording}
                disabled={!canStop}
              >
                <Square className="mr-2 h-4 w-4" aria-hidden="true" />
                {canStop ? 'Stop & use video' : `Recording... ${formatSeconds(elapsed)}`}
              </Button>
            ) : (
              <>
                <Button
                  type="button"
                  onClick={() => void startRecording()}
                  disabled={videoBusy !== null}
                  className="bg-brand text-white hover:bg-brand/90"
                >
                  <Camera className="mr-2 h-4 w-4" aria-hidden="true" />
                  {video ? 'Record a new video' : 'Record live video'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => videoInput.current?.click()}
                  disabled={videoBusy !== null}
                >
                  <Upload className="mr-2 h-4 w-4" aria-hidden="true" />
                  {video ? 'Replace with a file' : 'Upload video file'}
                </Button>
              </>
            )}
            {video && (
              <ul className="mt-2 space-y-1.5 rounded-lg border border-border bg-muted/40 p-3 text-xs">
                <li className="font-semibold">Video check</li>
                {videoChecks.map((check) => (
                  <li key={check.label} className="flex items-center gap-1.5">
                    <CheckCircle2
                      className={
                        check.ok ? 'h-3.5 w-3.5 text-emerald-600' : 'h-3.5 w-3.5 text-amber-500'
                      }
                      aria-hidden="true"
                    />
                    {check.label}
                  </li>
                ))}
                <li className="pt-1 text-muted-foreground">No sound is recorded.</li>
              </ul>
            )}
          </div>
        </div>
        <input
          ref={videoInput}
          type="file"
          accept="video/mp4,video/webm"
          className="hidden"
          onChange={(e) => void handleVideoFile(e)}
        />
      </section>
    </div>
  );
}
