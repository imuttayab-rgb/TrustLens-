/** Reusable UI rendering and interaction component: LiveVerificationWizard. */
'use client';

import { api } from '@/lib/api/client';
import type { FormError } from '@/lib/forms/use-api-form';
import { qk } from '@/lib/api/query-keys';
import { uploadFile } from '@/lib/upload';
import { useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import { Alert, Progress, Spinner, cn } from '@trustlens/ui';
import {
  ArrowRight,
  Camera,
  Check,
  CircleAlert,
  FileText,
  Hand,
  IdCard,
  Glasses,
  Lock,
  Megaphone,
  RefreshCw,
  ScanFace,
  ScanLine,
  ShieldCheck,
  Sun,
  UserRound,
  Users,
  type LucideIcon,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import * as React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useJobStatus } from '../hooks/use-job-status';
import { useLiveCapture, type CaptureView, type StatusChip } from './use-live-capture';
import {
  allCaptured,
  buildSteps,
  isCaptureStep,
  nextStepAfter,
  stepState,
  type CaptureStep,
  type Captured,
  type StepId,
  type StepState,
  type WizardStep,
} from './wizard-steps';

/**
 * Step-by-step live identity verification (CNIC front -> CNIC back -> face ->
 * ID beside face -> submit), one step at a time.
 *
 * - A step only completes when its live camera challenge passes; the wizard
 *   then moves to the next step on its own after a short "get ready" count.
 * - If a step does not pass (too dark, glare, blur, face not found, timeout)
 *   the seller stays on that step and sees the reason and a "Try again".
 * - Upload + submission are unchanged from the previous form: the same four
 *   private files and the same POST /api/v1/verification/identity body.
 *
 * Wording on this screen is deliberately factual: the server reads the card
 * with OCR, compares faces, and a human reviewer decides. It does not claim
 * NADRA validation, document authenticity or certified liveness.
 */

const PURPOSE: Record<CaptureStep, string> = {
  front: 'CNIC_FRONT',
  back: 'CNIC_BACK',
  face: 'SELFIE',
  hold: 'HOLD_ID',
};

const SHORT_LABEL: Record<CaptureStep, string> = {
  front: 'CNIC front',
  back: 'CNIC back',
  face: 'Face scan',
  hold: 'Hold ID',
};

interface StepCopy {
  title: string;
  start: string;
  tips: { icon: LucideIcon; text: string }[];
  /** Shown during the short countdown before the camera opens. */
  getReady: string;
}

const COPY: Record<CaptureStep, StepCopy> = {
  front: {
    title: 'Scan the front of your CNIC',
    start: 'Start CNIC front scan',
    getReady: 'Get your physical CNIC ready — FRONT side (photo and number) toward the camera.',
    tips: [
      { icon: IdCard, text: 'Use your physical card, not a photo or a screen' },
      { icon: ScanLine, text: 'Show all four corners of the card' },
      { icon: Hand, text: "Don't cover the photo or text with fingers" },
      { icon: Sun, text: 'Avoid lamps and window glare' },
    ],
  },
  back: {
    title: 'Scan the back of your CNIC',
    start: 'Start CNIC back scan',
    getReady: 'Turn your card over — BACK side (address and expiry date) toward the camera.',
    tips: [
      { icon: IdCard, text: 'Turn the card over to the back side' },
      { icon: FileText, text: 'Keep the expiry date clear and readable' },
      { icon: Hand, text: 'Hold the card flat and steady' },
      { icon: Sun, text: 'Avoid lamps and window glare' },
    ],
  },
  face: {
    title: 'Scan your face',
    start: 'Start face scan',
    getReady: 'Put the card down and look straight at the camera.',
    tips: [
      { icon: UserRound, text: 'Keep your whole face inside the oval' },
      { icon: Glasses, text: 'Remove sunglasses, mask or cap' },
      { icon: ScanFace, text: 'Follow the look up / look down prompt' },
      { icon: Sun, text: 'Face a window or lamp for even light' },
    ],
  },
  hold: {
    title: 'Hold your ID beside your face',
    start: 'Start ID-beside-face scan',
    getReady: 'Pick up your card and hold its FRONT next to your face.',
    tips: [
      { icon: UserRound, text: 'Keep your whole face inside the oval' },
      { icon: IdCard, text: 'Show all four corners of the card' },
      { icon: Hand, text: "Don't cover the photo or text with fingers" },
      { icon: Sun, text: 'Avoid lamps and window glare' },
    ],
  },
};

const AFTER_SUBMIT: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: FileText, title: 'Card details read', text: 'Number and expiry date are checked automatically.' },
  { icon: ScanFace, title: 'Face compared', text: 'Your live face is compared with the card photo.' },
  { icon: Users, title: 'Human review', text: 'A TrustLens reviewer makes the final decision.' },
  { icon: Megaphone, title: 'Ads go live', text: 'Your listings become public once approved.' },
];

const NO_FILES: Record<CaptureStep, File | null> = { front: null, back: null, face: null, hold: null };
const COUNTDOWN_SECONDS = 3;
const ADVANCE_DELAY_MS = 900;

/** Object URLs for captured photos, revoked when a photo changes or unmounts. */
function usePreviews(files: Record<CaptureStep, File | null>): Partial<Record<CaptureStep, string>> {
  const [urls, setUrls] = useState<Partial<Record<CaptureStep, string>>>({});
  useEffect(() => {
    const next: Partial<Record<CaptureStep, string>> = {};
    (Object.keys(files) as CaptureStep[]).forEach((key) => {
      const file = files[key];
      if (file) next[key] = URL.createObjectURL(file);
    });
    setUrls(next);
    return () => Object.values(next).forEach((url) => url && URL.revokeObjectURL(url));
  }, [files]);
  return urls;
}

export interface LiveVerificationWizardProps {
  holdEnabled: boolean;
  /**
   * Starting state for component tests and design previews only. The real
   * page passes none of these, and props cannot be set from a URL, so a
   * seller cannot use them to skip a live step. Even when used, Submit still
   * uploads only real File objects through the normal private pipeline.
   */
  initialStep?: StepId;
  initialConsent?: boolean;
  initialFiles?: Partial<Record<CaptureStep, File>>;
}

export function LiveVerificationWizard({
  holdEnabled,
  initialStep = 'consent',
  initialConsent = false,
  initialFiles,
}: LiveVerificationWizardProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const steps = useMemo(() => buildSteps(holdEnabled), [holdEnabled]);

  const [current, setCurrent] = useState<StepId>(initialStep);
  const [consent, setConsent] = useState(initialConsent);
  const [files, setFiles] = useState<Record<CaptureStep, File | null>>(() => ({ ...NO_FILES, ...initialFiles }));
  // Mirror of `files` for callbacks fired from camera/timer code.
  const filesRef = useRef(files);
  filesRef.current = files;
  const advanceTimerRef = useRef<number | null>(null);
  const [progress, setProgress] = useState<Partial<Record<CaptureStep, number>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<FormError | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [justCaptured, setJustCaptured] = useState<CaptureStep | null>(null);
  const [autoStart, setAutoStart] = useState<{ step: CaptureStep; seconds: number } | null>(null);
  const [secure, setSecure] = useState(false);

  const previews = usePreviews(files);
  const captured: Captured = {
    front: Boolean(files.front),
    back: Boolean(files.back),
    face: Boolean(files.face),
    hold: Boolean(files.hold),
  };
  const submitted = jobId !== null;
  const job = useJobStatus(jobId);
  const complete = job.data?.status === 'complete';
  const failed = job.data?.status === 'failed' || job.data?.status === 'not_found';

  // Only claim an encrypted connection when the page really is on HTTPS.
  // The local laptop demo runs on http://localhost, so it says "Private".
  useEffect(() => setSecure(window.location.protocol === 'https:'), []);

  const clearAdvance = useCallback(() => {
    if (advanceTimerRef.current !== null) window.clearTimeout(advanceTimerRef.current);
    advanceTimerRef.current = null;
  }, []);
  useEffect(() => clearAdvance, [clearAdvance]);

  const onCaptured = useCallback((mode: CaptureStep, file: File) => {
    const updated = { ...filesRef.current, [mode]: file };
    filesRef.current = updated;
    setFiles(updated);
    const next = nextStepAfter(steps, mode, {
      front: Boolean(updated.front),
      back: Boolean(updated.back),
      face: Boolean(updated.face),
      hold: Boolean(updated.hold),
    });
    setJustCaptured(mode);
    // Brief "captured" confirmation, then move on by itself. The next camera
    // opens after a short countdown so the seller can flip the card or put
    // it down (otherwise the FRONT could be captured again as the BACK).
    clearAdvance();
    advanceTimerRef.current = window.setTimeout(() => {
      advanceTimerRef.current = null;
      setJustCaptured(null);
      setCurrent(next);
      if (isCaptureStep(next)) setAutoStart({ step: next, seconds: COUNTDOWN_SECONDS });
    }, ADVANCE_DELAY_MS);
  }, [steps, clearAdvance]);

  const camera = useLiveCapture({ disabled: !consent || submitting || submitted, onCaptured });
  const { start: startCamera, stop: stopCamera } = camera;

  const beginCapture = useCallback((step: CaptureStep) => {
    clearAdvance();
    setAutoStart(null);
    setError(null);
    // A retake removes the old photo FIRST, so a previous frame can never be
    // submitted as the result of this new live attempt.
    const updated = { ...filesRef.current, [step]: null };
    filesRef.current = updated;
    setFiles(updated);
    void startCamera(step);
  }, [startCamera, clearAdvance]);

  // Countdown before the camera opens on an auto-advanced step.
  useEffect(() => {
    if (!autoStart) return;
    if (autoStart.step !== current) {
      setAutoStart(null);
      return;
    }
    if (autoStart.seconds <= 0) {
      beginCapture(autoStart.step);
      return;
    }
    const timer = window.setTimeout(
      () => setAutoStart((value) => (value ? { ...value, seconds: value.seconds - 1 } : value)),
      1000,
    );
    return () => window.clearTimeout(timer);
  }, [autoStart, current, beginCapture]);

  function goTo(step: StepId) {
    if (submitting || submitted) return;
    stopCamera();
    clearAdvance();
    setAutoStart(null);
    setJustCaptured(null);
    setCurrent(step);
  }

  async function onSubmit() {
    if (!consent || !allCaptured(steps, captured)) return;
    setError(null);
    setSubmitting(true);
    try {
      // Sequential on purpose (as before): honest per-file progress and no
      // competing multi-megabyte uploads on a slow mobile connection.
      const ids: Partial<Record<CaptureStep, string>> = {};
      for (const step of steps) {
        if (!isCaptureStep(step.id)) continue;
        const key = step.id;
        const file = files[key];
        if (!file) continue;
        ids[key] = await uploadFile(PURPOSE[key], file, {
          onProgress: (percent) => setProgress((p) => ({ ...p, [key]: percent })),
        });
      }
      const result = await api.POST('/api/v1/verification/identity', {
        body: {
          cnicFrontFileId: ids.front as string,
          cnicBackFileId: ids.back as string,
          selfieFileId: ids.face as string,
          ...(holdEnabled ? { holdIdFileId: ids.hold as string } : {}),
          biometricConsent: true,
        },
      });
      if (result.error) throw toApiError(result.error);
      const data = (result.data as { data: { jobId?: string } }).data;
      // A missing job id still means the API accepted the submission.
      setJobId(data.jobId ?? 'submitted');
      await queryClient.invalidateQueries({ queryKey: qk.verification.status });
    } catch (raw) {
      const apiError = toApiError(raw);
      setError({ message: apiError.message, requestId: apiError.requestId });
    } finally {
      setSubmitting(false);
      setProgress({});
    }
  }

  const index = Math.max(0, steps.findIndex((step) => step.id === current));
  const view = camera.view;
  const captureStep = isCaptureStep(current) ? current : null;
  const live = captureStep !== null && view.mode === captureStep && (view.status === 'active' || view.status === 'loading');
  const stepError = captureStep !== null && view.mode === captureStep && view.status === 'error' ? view.error : null;
  const countdown = autoStart && autoStart.step === current ? autoStart.seconds : null;
  const capturedOthers = steps
    .map((step) => step.id)
    .filter((id): id is CaptureStep => isCaptureStep(id) && id !== current && captured[id]);
  const previousCaptured = [...capturedOthers].reverse().find((id) => steps.findIndex((s) => s.id === id) < index);

  return (
    // Wider than the 4xl dashboard column so the camera and the instructions
    // can sit side by side, as in the approved design.
    <div className="relative left-1/2 w-[min(76rem,calc(100vw-2rem))] -translate-x-1/2 space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">Verify your identity</h1>
          <p className="mt-1.5 text-sm text-muted-foreground sm:text-base">
            A quick live camera check. Your ads go live after a reviewer approves it.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
            <Lock className="h-4 w-4" aria-hidden="true" />
            {secure ? 'Encrypted session' : 'Private session'}
          </span>
          <span className="rounded-full bg-primary/10 px-3.5 py-1.5 text-sm font-semibold text-primary">
            Step {index + 1} of {steps.length}
          </span>
        </div>
      </header>

      <WizardStepper
        steps={steps}
        current={current}
        captured={captured}
        submitted={submitted}
        onSelect={(id) => goTo(id)}
      />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:gap-y-0">
        {/* Camera / preview area */}
        <section className="lg:row-span-2" aria-label="Camera">
          {current === 'submit' ? (
            <ReviewGrid
              steps={steps}
              previews={previews}
              disabled={submitting || submitted}
              onRetake={(step) => goTo(step)}
            />
          ) : (
            <CameraStage
              step={captureStep}
              view={view}
              videoRef={camera.videoRef}
              live={live}
              preview={captureStep ? previews[captureStep] : undefined}
              countdown={countdown}
              getReady={captureStep ? COPY[captureStep].getReady : ''}
              justCaptured={justCaptured}
              error={stepError}
            />
          )}
          <canvas ref={camera.canvasRef} className="hidden" aria-hidden="true" />
        </section>

        {/* Instructions */}
        <section className="order-last rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6 lg:order-none lg:col-start-2 lg:row-start-1 lg:rounded-b-none lg:border-b-0 lg:pb-3">
          {current === 'consent' && <ConsentPanel consent={consent} disabled={submitting} onChange={(value) => {
            setConsent(value);
            // Withdrawing consent discards every captured photo; agreeing
            // again starts a completely fresh session.
            if (!value) {
              stopCamera();
              filesRef.current = NO_FILES;
              setFiles(NO_FILES);
            }
          }} />}

          {captureStep && (
            <>
              <h2 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">{COPY[captureStep].title}</h2>
              <ul className="mt-4 space-y-3">
                {COPY[captureStep].tips.map(({ icon: Icon, text }) => (
                  <li key={text} className="flex items-center gap-3 text-sm text-foreground/90">
                    <Icon className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                    {text}
                  </li>
                ))}
              </ul>
            </>
          )}

          {current === 'submit' && (
            <>
              <h2 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
                {submitted ? 'Submitted for review' : 'Review and submit'}
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {submitted
                  ? 'Your photos were sent privately. You can leave this page; your status updates on its own.'
                  : 'Check that every photo is clear. Tap any photo to retake it, then submit.'}
              </p>
            </>
          )}

          {captureStep && capturedOthers.length > 0 && (
            <div className="mt-5 border-t border-border pt-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-foreground">Already captured</h3>
                {previousCaptured && !live && (
                  <button
                    type="button"
                    onClick={() => goTo(previousCaptured)}
                    className="text-sm font-medium text-primary underline underline-offset-4"
                  >
                    Retake
                  </button>
                )}
              </div>
              <div className="mt-3 flex flex-wrap gap-3">
                {capturedOthers.map((id) => (
                  <Thumbnail
                    key={id}
                    label={SHORT_LABEL[id]}
                    src={previews[id]}
                    disabled={live}
                    onClick={() => goTo(id)}
                  />
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Actions */}
        <section className="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6 lg:col-start-2 lg:row-start-2 lg:rounded-t-none lg:border-t-0 lg:pt-3">
          {current === 'consent' && (
            <PrimaryButton disabled={!consent} onClick={() => {
              const next = nextStepAfter(steps, 'consent', captured);
              setCurrent(next);
              if (isCaptureStep(next)) setAutoStart({ step: next, seconds: COUNTDOWN_SECONDS });
            }}>
              Agree and continue <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </PrimaryButton>
          )}

          {captureStep && (
            <CaptureActions
              step={captureStep}
              view={view}
              live={live}
              hasPhoto={captured[captureStep]}
              countdown={countdown}
              onStart={() => beginCapture(captureStep)}
              onContinue={() => goTo(nextStepAfter(steps, captureStep, captured))}
            />
          )}

          {current === 'submit' && (
            <SubmitActions
              steps={steps}
              captured={captured}
              progress={progress}
              submitting={submitting}
              submitted={submitted}
              complete={complete}
              failed={failed}
              error={error}
              onSubmit={() => void onSubmit()}
              onDone={() => {
                router.push('/dashboard');
                router.refresh();
              }}
            />
          )}

          <div className="mt-4 flex items-start gap-3 rounded-xl bg-primary/5 p-3.5 text-sm text-muted-foreground">
            <Lock className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
            <p>
              Private &amp; protected. Only the TrustLens review team can see these images. Deleted 90 days after a
              decision.
            </p>
          </div>
        </section>
      </div>

      <section className="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="after-submit">
        <h2 id="after-submit" className="text-lg font-bold tracking-tight text-foreground sm:text-xl">
          What happens after you submit
        </h2>
        <div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-4 lg:divide-x lg:divide-border">
          {AFTER_SUBMIT.map(({ icon: Icon, title, text }, i) => (
            <div key={title} className={cn('flex items-start gap-3', i > 0 && 'lg:pl-5')}>
              <Icon className="h-8 w-8 shrink-0 text-primary" strokeWidth={1.6} aria-hidden="true" />
              <div>
                <p className="font-semibold text-foreground">{title}</p>
                <p className="mt-0.5 text-sm text-muted-foreground">{text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// ── Stepper ─────────────────────────────────────────────────────────────

export function WizardStepper({
  steps,
  current,
  captured,
  submitted,
  onSelect,
}: {
  steps: WizardStep[];
  current: StepId;
  captured: Captured;
  submitted: boolean;
  onSelect?: (id: StepId) => void;
}) {
  const states: StepState[] = steps.map((step) => stepState(step.id, current, captured, submitted));
  const activeIndex = Math.max(0, steps.findIndex((step) => step.id === current));
  const sub: Record<StepState, string> = { complete: 'Complete', active: 'In progress', pending: 'Pending' };

  return (
    <nav aria-label="Verification steps" className="rounded-2xl border border-border bg-card px-4 py-4 shadow-sm sm:px-6">
      {/* Phone: compact dots + "Step 5 of 6 - Hold ID" */}
      <div className="sm:hidden">
        <ol className="flex items-center">
          {steps.map((step, i) => (
            <li key={step.id} className={cn('flex items-center', i < steps.length - 1 && 'flex-1')}>
              <StepDot state={states[i]!} number={i + 1} small />
              {i < steps.length - 1 && (
                <span className={cn('mx-1 h-0.5 flex-1 rounded', states[i] === 'complete' ? 'bg-primary' : 'bg-border')} />
              )}
            </li>
          ))}
        </ol>
        <p className="mt-3 text-center text-sm font-medium text-foreground">
          Step {activeIndex + 1} of {steps.length} - {steps[activeIndex]?.label}
        </p>
      </div>

      {/* Tablet / desktop: full labels */}
      <ol className="hidden items-center sm:flex">
        {steps.map((step, i) => {
          const state = states[i]!;
          const clickable = Boolean(onSelect) && state === 'complete' && step.id !== 'submit' && !submitted;
          const body = (
            <>
              <StepDot state={state} number={i + 1} />
              <span className="ml-2.5 hidden text-left md:block">
                <span className="flex items-baseline gap-1.5">
                  {state === 'complete' && <span className="text-xs font-semibold text-primary">{i + 1}</span>}
                  <span className="text-sm font-semibold text-foreground">{step.label}</span>
                </span>
                <span className={cn('block text-xs', state === 'active' ? 'font-medium text-primary' : 'text-muted-foreground')}>
                  {sub[state]}
                </span>
              </span>
            </>
          );
          return (
            <li key={step.id} className={cn('flex items-center', i < steps.length - 1 && 'flex-1')}
              aria-current={state === 'active' ? 'step' : undefined}>
              {clickable ? (
                <button type="button" onClick={() => onSelect?.(step.id)} className="flex items-center rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  {body}
                </button>
              ) : (
                <span className="flex items-center">{body}</span>
              )}
              {i < steps.length - 1 && (
                <span className={cn('mx-3 h-0.5 min-w-4 flex-1 rounded', state === 'complete' ? 'bg-primary' : 'bg-border')} aria-hidden="true" />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function StepDot({ state, number, small = false }: { state: StepState; number: number; small?: boolean }) {
  const size = small ? 'h-8 w-8 text-xs' : 'h-10 w-10 text-sm';
  if (state === 'complete') {
    return (
      <span className={cn('grid shrink-0 place-items-center rounded-full bg-primary text-primary-foreground', size)}>
        <Check className={small ? 'h-4 w-4' : 'h-5 w-5'} strokeWidth={3} aria-hidden="true" />
        <span className="sr-only">Step {number} complete</span>
      </span>
    );
  }
  if (state === 'active') {
    return (
      <span className={cn('grid shrink-0 place-items-center rounded-full border-2 border-primary bg-card font-semibold text-primary ring-4 ring-primary/15', size)}>
        {number}
      </span>
    );
  }
  return (
    <span className={cn('grid shrink-0 place-items-center rounded-full bg-muted font-semibold text-muted-foreground', size)}>
      {number}
    </span>
  );
}

// ── Camera area ─────────────────────────────────────────────────────────

function CameraStage({
  step,
  view,
  videoRef,
  live,
  preview,
  countdown,
  getReady,
  justCaptured,
  error,
}: {
  step: CaptureStep | null;
  view: CaptureView;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  live: boolean;
  preview: string | undefined;
  countdown: number | null;
  getReady: string;
  justCaptured: CaptureStep | null;
  error: string | null;
}) {
  const isCardStep = step === 'front' || step === 'back';
  const mirrored = step === 'face' || step === 'hold';
  const showPreview = Boolean(preview) && !live;
  const active = live && view.status === 'active';
  // CNIC steps: the video is shown whole (no cropping) inside a box with the
  // camera's real shape, so the dashed guide matches exactly the area that
  // analyzeDocumentFrame measures. Face steps fill the panel (cropping the
  // edges is harmless there; face detection always uses the whole frame).
  const cardFrameStyle = isCardStep ? { aspectRatio: String(view.aspect) } : undefined;

  return (
    <div
      className="relative aspect-[3/4] overflow-hidden rounded-2xl border border-border bg-slate-900 shadow-sm sm:aspect-[16/10] lg:aspect-auto lg:h-full lg:min-h-[34rem]"
    >
      <div className={cn('absolute', isCardStep ? 'inset-x-0 top-1/2 max-h-full -translate-y-1/2' : 'inset-0')} style={cardFrameStyle}>
        {/* Always mounted, so the camera stream always has a target element. */}
        <video
          ref={videoRef}
          muted
          playsInline
          className={cn(
            'absolute inset-0 h-full w-full',
            isCardStep ? 'object-contain' : 'object-cover',
            mirrored && 'scale-x-[-1]',
            !active && 'invisible',
          )}
        />
        {/* Framing guides: live, or as a hint before the camera starts. Hidden
            over a captured photo, where they would not line up. */}
        {step && !showPreview && (
          <Guides kind={isCardStep ? 'card' : step === 'face' ? 'face' : 'hold'} dim={!active} />
        )}
      </div>

      {showPreview && (
        <img src={preview} alt={`Captured ${step ? SHORT_LABEL[step] : 'photo'}`} className="absolute inset-0 h-full w-full object-contain" />
      )}

      {!step && (
        <div className="absolute inset-0 grid place-items-center bg-gradient-to-br from-slate-800 via-slate-900 to-teal-950 p-6 text-center text-white">
          <div>
            <ShieldCheck className="mx-auto h-14 w-14 text-teal-300" strokeWidth={1.5} aria-hidden="true" />
            <p className="mt-4 text-lg font-semibold">Your camera turns on only after you agree.</p>
            <p className="mt-1 text-sm text-white/70">CNIC front, CNIC back, a face scan and a photo with your ID.</p>
          </div>
        </div>
      )}

      {active && (
        <span className="absolute left-3 top-3 inline-flex items-center gap-2 rounded-lg bg-black/65 px-3 py-1.5 text-sm font-semibold text-white backdrop-blur">
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-500" aria-hidden="true" /> LIVE
        </span>
      )}

      {showPreview && !justCaptured && (
        <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-lg bg-emerald-600/90 px-3 py-1.5 text-sm font-semibold text-white">
          <Check className="h-4 w-4" strokeWidth={3} aria-hidden="true" /> Captured
        </span>
      )}

      {step && !live && !showPreview && countdown === null && !error && (
        <div className="absolute inset-0 grid place-items-center p-6 text-center text-white">
          <div className="rounded-2xl bg-black/55 px-6 py-5 backdrop-blur">
            <Camera className="mx-auto h-9 w-9 text-teal-300" aria-hidden="true" />
            <p className="mt-2 font-semibold">Camera is off</p>
            <p className="text-sm text-white/75">Press &ldquo;{COPY[step].start}&rdquo; to begin.</p>
          </div>
        </div>
      )}

      {countdown !== null && step && !live && (
        <div className="absolute inset-0 grid place-items-center bg-slate-950/70 p-6 text-center text-white" aria-live="polite">
          <div>
            <p className="text-6xl font-bold tabular-nums">{Math.max(countdown, 1)}</p>
            <p className="mx-auto mt-3 max-w-sm text-base font-medium">{getReady}</p>
          </div>
        </div>
      )}

      {live && view.status === 'loading' && (
        <div className="absolute inset-0 grid place-items-center text-white">
          <span className="inline-flex items-center gap-2 rounded-xl bg-black/60 px-4 py-2.5 text-sm">
            <Spinner label="Opening camera" /> Opening camera…
          </span>
        </div>
      )}

      {justCaptured && (
        <div className="absolute inset-0 grid place-items-center bg-emerald-950/45 text-white" aria-live="polite">
          <span className="inline-flex items-center gap-2 rounded-2xl bg-emerald-600 px-5 py-3 text-base font-semibold shadow-lg">
            <Check className="h-5 w-5" strokeWidth={3} aria-hidden="true" /> {SHORT_LABEL[justCaptured]} captured
          </span>
        </div>
      )}

      {error && !live && step && countdown === null && (
        // The step did not pass: stay here and say why (too dark, glare,
        // blur, face not found, timeout). The seller retries the same step.
        <div className="absolute inset-0 grid place-items-center bg-slate-950/60 p-6 text-center text-white" role="alert">
          <div className="max-w-md rounded-2xl bg-black/70 px-6 py-5 backdrop-blur">
            <CircleAlert className="mx-auto h-9 w-9 text-amber-300" aria-hidden="true" />
            <p className="mt-2 text-lg font-semibold">Retry needed</p>
            <p className="mt-1 text-sm text-white/85">{error}</p>
          </div>
        </div>
      )}

      {active && (
        <div className="absolute inset-x-3 bottom-3 space-y-2 sm:inset-x-6 sm:bottom-4" aria-live="polite">
          <div className="mx-auto flex max-w-xl items-center gap-3 rounded-xl bg-black/70 px-4 py-3 text-white backdrop-blur">
            <StageRing stage={view.stage} />
            <div className="min-w-0">
              <p className="font-semibold leading-snug">{view.prompt}</p>
              <p className="text-xs text-white/75">{view.hint}</p>
            </div>
          </div>
          <StatusChips chips={view.chips} />
        </div>
      )}
    </div>
  );
}

function Guides({ kind, dim }: { kind: 'card' | 'face' | 'hold'; dim: boolean }) {
  const tone = dim ? 'opacity-40' : 'opacity-100';
  if (kind === 'card') {
    // Same region analyzeDocumentFrame measures: 12.5%-87.5% wide, 20%-80% high.
    return (
      <div className={cn('pointer-events-none absolute bottom-[20%] left-[12.5%] right-[12.5%] top-[20%]', tone)} aria-hidden="true">
        <div className="absolute inset-0 rounded-xl border-2 border-dashed border-white/80" />
        <Corners />
      </div>
    );
  }
  return (
    <div className={cn('pointer-events-none absolute inset-0', tone)} aria-hidden="true">
      <div
        className={cn(
          'absolute top-[12%] h-[64%] rounded-[50%] border-2 border-dashed border-white/90',
          kind === 'face' ? 'left-1/2 w-[34%] -translate-x-1/2 sm:w-[26%]' : 'left-[22%] w-[34%] sm:left-[28%] sm:w-[22%]',
        )}
      />
      {kind === 'hold' && (
        <div className="absolute left-[62%] top-[30%] h-[30%] w-[30%] sm:left-[60%] sm:w-[24%]">
          <div className="absolute inset-0 rounded-lg border-2 border-teal-300/90 bg-teal-300/10" />
          <Corners />
        </div>
      )}
    </div>
  );
}

function Corners() {
  const base = 'absolute h-5 w-5 border-teal-300';
  return (
    <>
      <span className={cn(base, '-left-1 -top-1 rounded-tl-lg border-l-[3px] border-t-[3px]')} />
      <span className={cn(base, '-right-1 -top-1 rounded-tr-lg border-r-[3px] border-t-[3px]')} />
      <span className={cn(base, '-bottom-1 -left-1 rounded-bl-lg border-b-[3px] border-l-[3px]')} />
      <span className={cn(base, '-bottom-1 -right-1 rounded-br-lg border-b-[3px] border-r-[3px]')} />
    </>
  );
}

function StageRing({ stage }: { stage: number }) {
  const done = Math.min(Math.max(stage, 0), 4);
  const radius = 18;
  const length = 2 * Math.PI * radius;
  return (
    <span className="relative grid h-12 w-12 shrink-0 place-items-center" aria-label={`Movement ${done} of 4 done`}>
      <svg viewBox="0 0 44 44" className="absolute inset-0 h-12 w-12 -rotate-90" aria-hidden="true">
        <circle cx="22" cy="22" r={radius} fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="4" />
        <circle
          cx="22"
          cy="22"
          r={radius}
          fill="none"
          stroke="rgb(94 234 212)"
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={length}
          strokeDashoffset={length * (1 - done / 4)}
          className="transition-[stroke-dashoffset] duration-300"
        />
      </svg>
      <span className="text-xs font-semibold tabular-nums">{done}/4</span>
    </span>
  );
}

export function StatusChips({ chips }: { chips: StatusChip[] }) {
  return (
    <ul className="flex flex-wrap justify-center gap-2">
      {chips.map((chip) => (
        <li key={chip.key} className="inline-flex items-center gap-2 rounded-lg bg-black/65 px-3 py-1.5 text-xs font-medium text-white backdrop-blur sm:text-sm">
          {chip.tone === 'ok' ? (
            <span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-500"><Check className="h-3 w-3" strokeWidth={3.5} aria-hidden="true" /></span>
          ) : chip.tone === 'warn' ? (
            <span className="grid h-5 w-5 place-items-center rounded-full bg-amber-400 text-[11px] font-bold text-black" aria-hidden="true">!</span>
          ) : (
            <span className="h-5 w-5 rounded-full border-2 border-white/40" aria-hidden="true" />
          )}
          <span>{chip.label}</span>
          <span className="sr-only">{chip.tone === 'ok' ? '(passed)' : chip.tone === 'warn' ? '(needs attention)' : '(checking)'}</span>
        </li>
      ))}
    </ul>
  );
}

// ── Right-hand panels ───────────────────────────────────────────────────

function ConsentPanel({ consent, disabled, onChange }: { consent: boolean; disabled: boolean; onChange: (value: boolean) => void }) {
  const items: { icon: LucideIcon; text: string }[] = [
    { icon: IdCard, text: 'Your physical CNIC (front and back)' },
    { icon: Sun, text: 'A well-lit place without strong glare' },
    { icon: Camera, text: 'A camera (a phone camera usually works best)' },
    { icon: ScanFace, text: 'About two minutes' },
  ];
  return (
    <>
      <h2 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">Before you start</h2>
      <ul className="mt-4 space-y-3">
        {items.map(({ icon: Icon, text }) => (
          <li key={text} className="flex items-center gap-3 text-sm text-foreground/90">
            <Icon className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
            {text}
          </li>
        ))}
      </ul>
      <div className="mt-5 border-t border-border pt-4">
        <label htmlFor="wizard-consent" className="flex cursor-pointer items-start gap-3">
          <input
            id="wizard-consent"
            type="checkbox"
            checked={consent}
            disabled={disabled}
            onChange={(event) => onChange(event.target.checked)}
            aria-describedby="wizard-consent-detail"
            className="mt-0.5 h-4 w-4 shrink-0 rounded border-input accent-[hsl(var(--primary))]"
          />
          <span className="text-sm font-medium text-foreground">
            I consent to live ID and face camera capture and comparing my face with the ID portrait.
          </span>
        </label>
        <p id="wizard-consent-detail" className="mt-2 pl-7 text-xs text-muted-foreground">
          Movement checks run on this device. Only the final front, back, face and holding-card photos are sent to
          private storage for the identity check and staff review. This is not a NADRA record check or a certified
          liveness test.
        </p>
      </div>
    </>
  );
}

function PrimaryButton({
  children,
  disabled,
  busy = false,
  onClick,
}: {
  children: React.ReactNode;
  disabled?: boolean;
  /** Working (e.g. auto-capture running): full colour, but not clickable. */
  busy?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-disabled={busy || undefined}
      aria-busy={busy || undefined}
      onClick={busy ? undefined : onClick}
      className={cn(
        'flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-base font-semibold text-primary-foreground shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60',
        busy ? 'cursor-wait' : 'hover:bg-primary/90',
      )}
    >
      {children}
    </button>
  );
}

function SecondaryButton({ children, disabled, onClick }: { children: React.ReactNode; disabled?: boolean; onClick?: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="mt-3 flex h-12 w-full items-center justify-center gap-2 rounded-xl border-2 border-primary/70 bg-card px-4 text-base font-semibold text-primary transition hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function CaptureActions({
  step,
  view,
  live,
  hasPhoto,
  countdown,
  onStart,
  onContinue,
}: {
  step: CaptureStep;
  view: CaptureView;
  live: boolean;
  hasPhoto: boolean;
  countdown: number | null;
  onStart: () => void;
  onContinue: () => void;
}) {
  if (live) {
    return (
      <>
        <PrimaryButton busy>
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground/40 border-t-primary-foreground" aria-hidden="true" />
          {view.status === 'loading' ? 'Opening camera…' : 'Capturing automatically...'}
        </PrimaryButton>
        <SecondaryButton onClick={onStart}>Retake photo</SecondaryButton>
      </>
    );
  }
  if (countdown !== null) {
    return (
      <>
        <PrimaryButton onClick={onStart}>
          <Camera className="h-5 w-5" aria-hidden="true" /> Start now
        </PrimaryButton>
        <p className="mt-3 text-center text-sm text-muted-foreground">Camera opens in {Math.max(countdown, 1)}…</p>
      </>
    );
  }
  if (hasPhoto) {
    return (
      <>
        <PrimaryButton onClick={onContinue}>
          Continue <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </PrimaryButton>
        <SecondaryButton onClick={onStart}>Retake photo</SecondaryButton>
      </>
    );
  }
  return (
    <PrimaryButton onClick={onStart}>
      {view.status === 'error' && view.mode === step ? (
        <><RefreshCw className="h-5 w-5" aria-hidden="true" /> Try again</>
      ) : (
        <><Camera className="h-5 w-5" aria-hidden="true" /> {COPY[step].start}</>
      )}
    </PrimaryButton>
  );
}

function SubmitActions({
  steps,
  captured,
  progress,
  submitting,
  submitted,
  complete,
  failed,
  error,
  onSubmit,
  onDone,
}: {
  steps: WizardStep[];
  captured: Captured;
  progress: Partial<Record<CaptureStep, number>>;
  submitting: boolean;
  submitted: boolean;
  complete: boolean;
  failed: boolean;
  error: FormError | null;
  onSubmit: () => void;
  onDone: () => void;
}) {
  const ready = allCaptured(steps, captured);
  if (submitted) {
    return (
      <div className="space-y-4">
        {!complete && !failed && (
          <div className="flex items-center gap-3 rounded-xl bg-muted p-3.5 text-sm">
            <Spinner label="Checking your documents" />
            <span>Checking your documents… a reviewer will make the final decision.</span>
          </div>
        )}
        {complete && (
          <Alert tone="success" title="Documents received">
            Your card and face photos were received. Your identity stays pending until a TrustLens reviewer decides.
          </Alert>
        )}
        {failed && (
          <Alert tone="warning" title="We could not finish the check automatically">
            A reviewer will look at your photos by hand. You do not need to scan again.
          </Alert>
        )}
        <PrimaryButton onClick={onDone}>Back to dashboard</PrimaryButton>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {error && <Alert tone="error" requestId={error.requestId}>{error.message}</Alert>}
      {submitting && steps.filter((s) => isCaptureStep(s.id)).map((s) => {
        const key = s.id as CaptureStep;
        return <Progress key={key} value={progress[key] ?? 0} label={`Uploading ${SHORT_LABEL[key]}`} />;
      })}
      <PrimaryButton disabled={!ready || submitting} onClick={onSubmit}>
        {submitting ? (
          <><span className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground/40 border-t-primary-foreground" aria-hidden="true" /> Uploading…</>
        ) : (
          <><ShieldCheck className="h-5 w-5" aria-hidden="true" /> Submit for verification</>
        )}
      </PrimaryButton>
      {!ready && <p className="text-center text-sm text-muted-foreground">Complete every step before submitting.</p>}
    </div>
  );
}

function Thumbnail({ label, src, disabled, onClick }: { label: string; src: string | undefined; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={`Retake ${label}`}
      className="group relative w-[6.5rem] rounded-xl border border-border bg-card p-1.5 text-center shadow-sm transition hover:border-primary disabled:opacity-60"
    >
      <span className="block aspect-[4/3] overflow-hidden rounded-lg bg-muted">
        {src && <img src={src} alt="" className="h-full w-full object-cover" />}
      </span>
      <span className="absolute right-0.5 top-0.5 grid h-5 w-5 place-items-center rounded-full bg-emerald-500 text-white ring-2 ring-card">
        <Check className="h-3 w-3" strokeWidth={3.5} aria-hidden="true" />
      </span>
      <span className="mt-1 block text-xs text-foreground">{label}</span>
    </button>
  );
}

function ReviewGrid({
  steps,
  previews,
  disabled,
  onRetake,
}: {
  steps: WizardStep[];
  previews: Partial<Record<CaptureStep, string>>;
  disabled: boolean;
  onRetake: (step: CaptureStep) => void;
}) {
  const ids = steps.map((s) => s.id).filter(isCaptureStep);
  return (
    <div className="grid grid-cols-2 gap-3 rounded-2xl border border-border bg-card p-3 shadow-sm sm:gap-4 sm:p-4">
      {ids.map((id) => (
        <figure key={id} className="overflow-hidden rounded-xl border border-border bg-muted">
          <div className="relative aspect-[4/3] bg-slate-900">
            {previews[id] && <img src={previews[id]} alt={`Captured ${SHORT_LABEL[id]}`} className="h-full w-full object-contain" />}
            <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-md bg-emerald-600/90 px-2 py-0.5 text-xs font-semibold text-white">
              <Check className="h-3 w-3" strokeWidth={3} aria-hidden="true" /> {SHORT_LABEL[id]}
            </span>
          </div>
          <figcaption className="flex items-center justify-between bg-card px-3 py-2 text-sm">
            <span className="font-medium text-foreground">{SHORT_LABEL[id]}</span>
            {!disabled && (
              <button type="button" onClick={() => onRetake(id)} className="inline-flex items-center gap-1 text-primary underline underline-offset-4">
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Retake
              </button>
            )}
          </figcaption>
        </figure>
      ))}
    </div>
  );
}
