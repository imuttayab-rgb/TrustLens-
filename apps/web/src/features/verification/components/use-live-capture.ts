/** Reusable UI rendering and interaction component: use live capture. */
'use client';

import type { FaceLandmarker } from '@mediapipe/tasks-vision';
import { imageFileSchema } from '@trustlens/validation';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  advanceChallenge,
  newMotionChallenge,
  observePitch,
  opposite,
  type ChallengeStage,
  type MotionChallenge,
} from './face-challenge';
import { observeHolderPitch } from './hold-face-challenge';
import {
  advanceDocumentChallenge,
  analyzeDocumentFrame,
  documentQualityChecks,
  newDocumentChallenge,
  oppositeDirection,
  type DocumentChallenge,
} from './id-scan-challenge';
import { analyzeLighting, lightingIssue } from './scan-lighting';
import type { CaptureStep } from './wizard-steps';

/**
 * One camera, four live capture steps (CNIC front, CNIC back, face, ID beside
 * face) for the step-by-step identity wizard.
 *
 * This reuses the SAME pure challenge rules as LiveIdScan / LiveFaceScan /
 * HoldIdFaceScan (id-scan-challenge, face-challenge, hold-face-challenge), so
 * the wizard is a new layout, not a weaker check. Security properties kept:
 *  - no gallery/file input; every image comes from this live camera session;
 *  - a retake clears the old photo before the camera opens;
 *  - stored JPEGs are never mirrored (card text and face must stay original);
 *  - the face model and WASM are served locally, nothing goes to a third party.
 *
 * All of this is client-side guidance. A virtual camera or a modified browser
 * can bypass it, so the backend still runs OCR / face comparison and keeps
 * unclear evidence in human review. It is NOT certified liveness (PAD) and NOT
 * proof that a CNIC is authentic.
 */

export type CaptureStatus = 'idle' | 'loading' | 'active' | 'error';
export type ChipTone = 'ok' | 'warn' | 'idle';

export interface StatusChip {
  key: string;
  label: string;
  tone: ChipTone;
}

export interface CaptureView {
  mode: CaptureStep | null;
  status: CaptureStatus;
  /** What the seller should do right now. */
  prompt: string;
  /** Live quality hint or retry reason for the current frame. */
  hint: string;
  /** Completed movement stages, 0-4, for the progress ring. */
  stage: number;
  chips: StatusChip[];
  error: string | null;
  /** Width / height of the real camera frame, so guides line up with it. */
  aspect: number;
}

interface Options {
  disabled: boolean;
  onCaptured: (mode: CaptureStep, file: File) => void;
}

const MODEL = '/face-scan/face_landmarker.task';
const WASM = '/face-scan/wasm';
// Same per-step limits as the original single-step components.
const TIMEOUT_MS: Record<CaptureStep, number> = { front: 45_000, back: 45_000, face: 35_000, hold: 50_000 };
const CARD_TICK_MS = 180;
const FACE_TICK_MS = 140;
const DEFAULT_ASPECT = 16 / 9;
const STAGE_ORDER = ['center', 'first', 'second', 'return', 'complete'] as const;

const DEFAULT_ISSUE: Record<CaptureStep, string> = {
  front: 'Keep the whole card inside the frame and follow the left / right prompt.',
  back: 'Keep the whole card inside the frame and follow the left / right prompt.',
  face: 'Keep one face inside the oval and follow the head movement prompt.',
  hold: 'Keep your face and the card in view and follow the head movement prompt.',
};

const IDLE_VIEW: CaptureView = {
  mode: null,
  status: 'idle',
  prompt: '',
  hint: '',
  stage: 0,
  chips: [],
  error: null,
  aspect: DEFAULT_ASPECT,
};

function isCard(mode: CaptureStep): mode is 'front' | 'back' {
  return mode === 'front' || mode === 'back';
}

function stageIndex(stage: ChallengeStage | DocumentChallenge['stage']): number {
  return Math.max(0, STAGE_ORDER.indexOf(stage));
}

export function initialChips(mode: CaptureStep): StatusChip[] {
  if (isCard(mode)) {
    return [
      { key: 'light', label: 'Good lighting', tone: 'idle' },
      { key: 'glare', label: 'Low glare', tone: 'idle' },
      { key: 'sharp', label: 'Text sharp', tone: 'idle' },
    ];
  }
  return [
    { key: 'face', label: 'Face in frame', tone: 'idle' },
    ...(mode === 'hold' ? [{ key: 'card', label: 'Card photo seen', tone: 'idle' as const }] : []),
    { key: 'light', label: 'Good lighting', tone: 'idle' },
    { key: 'glare', label: 'Low glare', tone: 'idle' },
  ];
}

export function promptFor(mode: CaptureStep, challenge: DocumentChallenge | MotionChallenge | null): string {
  if (!challenge) return '';
  if (isCard(mode)) {
    const doc = challenge as DocumentChallenge;
    if (doc.stage === 'center') return `Center the ${mode} of your card in the frame and hold still.`;
    if (doc.stage === 'first') return `Move the card ${doc.first} inside the frame; hold still.`;
    if (doc.stage === 'second') return `Now move the card ${oppositeDirection(doc.first)}; hold still.`;
    if (doc.stage === 'return') return 'Return the card to the center; hold still for capture.';
    return 'Card captured.';
  }
  const motion = challenge as MotionChallenge;
  if (mode === 'hold') {
    if (motion.stage === 'center') return 'Hold the card next to your face and keep still';
    if (motion.stage === 'first') return `Keep the card beside your face; look ${motion.first} and hold.`;
    if (motion.stage === 'second') return `Keep the card visible; look ${opposite(motion.first)} and hold.`;
    if (motion.stage === 'return') return 'Look straight ahead; keep the card and your face visible.';
    return 'Photo with ID captured.';
  }
  if (motion.stage === 'center') return 'Look straight at the camera and hold still.';
  if (motion.stage === 'first') return `Look ${motion.first} and hold still.`;
  if (motion.stage === 'second') return `Look ${opposite(motion.first)} and hold still.`;
  if (motion.stage === 'return') return 'Look straight ahead again and hold still.';
  return 'Face scan captured.';
}

function constraints(mode: CaptureStep): MediaTrackConstraints {
  // `ideal`, never `exact`: most laptops have one webcam and no rear camera,
  // and the step must still work there.
  return {
    facingMode: { ideal: isCard(mode) ? 'environment' : 'user' },
    width: { ideal: 1280 },
    height: { ideal: 720 },
  };
}

const FILE_NAME: Record<CaptureStep, string> = {
  front: 'live-cnic-front.jpg',
  back: 'live-cnic-back.jpg',
  face: 'live-face.jpg',
  hold: 'hold-id-beside-face.jpg',
};

export function useLiveCapture({ disabled, onCaptured }: Options) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const modelRef = useRef<FaceLandmarker | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Every start/stop bumps the session. Late async work (camera permission,
  // model download, toBlob) from an older session is ignored, so a retake
  // can never be overwritten by a frame from the previous attempt.
  const sessionRef = useRef(0);
  const modeRef = useRef<CaptureStep | null>(null);
  const startedRef = useRef(0);
  const lastVideoTimeRef = useRef(-1);
  const lastIssueRef = useRef('');
  const docRef = useRef<DocumentChallenge | null>(null);
  const motionRef = useRef<MotionChallenge | null>(null);
  const mountedRef = useRef(true);
  const disabledRef = useRef(disabled);
  disabledRef.current = disabled;
  const onCapturedRef = useRef(onCaptured);
  onCapturedRef.current = onCaptured;
  const [view, setView] = useState<CaptureView>(IDLE_VIEW);

  /** Release the camera without touching React state. */
  const halt = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const fail = useCallback((message: string) => {
    sessionRef.current += 1;
    halt();
    if (mountedRef.current) setView((v) => ({ ...v, status: 'error', error: message }));
  }, [halt]);

  const stop = useCallback(() => {
    sessionRef.current += 1;
    halt();
    if (mountedRef.current) setView((v) => ({ ...v, status: 'idle' }));
  }, [halt]);

  const capture = useCallback((mode: CaptureStep) => {
    const video = videoRef.current;
    if (!video?.videoWidth || !video.videoHeight) {
      fail('Could not read the camera frame. Please try again.');
      return;
    }
    // Card and hold-ID frames are capped at 1600 px wide (as before). The face
    // frame keeps the camera's full resolution for the server face comparison.
    const scale = mode === 'face' ? 1 : Math.min(1, 1600 / video.videoWidth);
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      fail('Could not save the camera frame. Please try again.');
      return;
    }
    // Unmirrored on purpose: only the on-screen preview is mirrored.
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    sessionRef.current += 1;
    const session = sessionRef.current;
    halt();
    canvas.toBlob((blob) => {
      if (!mountedRef.current || disabledRef.current || session !== sessionRef.current) return;
      if (!blob) {
        fail('Camera capture failed. Please try again.');
        return;
      }
      const file = new File([blob], FILE_NAME[mode], { type: 'image/jpeg' });
      const parsed = imageFileSchema.safeParse(file);
      if (!parsed.success) {
        fail(parsed.error.issues[0]?.message ?? 'This photo could not be used. Please try again.');
        return;
      }
      setView((v) => ({ ...v, status: 'idle', error: null, stage: 4 }));
      onCapturedRef.current(mode, file);
    }, 'image/jpeg', mode === 'face' ? 0.86 : 0.9);
  }, [fail, halt]);

  /** One CNIC frame: light / glare / sharpness, then the left-right challenge. */
  const cardFrame = useCallback((mode: 'front' | 'back', video: HTMLVideoElement, canvas: HTMLCanvasElement) => {
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) throw new Error('2D canvas unavailable');
    // Only a small 320x240 grid is analysed, on this device. No video is
    // recorded or uploaded.
    canvas.width = 320;
    canvas.height = 240;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const quality = analyzeDocumentFrame(ctx.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height);
    const next = advanceDocumentChallenge(docRef.current ?? newDocumentChallenge(mode, 'left'), quality, performance.now());
    docRef.current = next;
    lastIssueRef.current = quality.okay ? '' : quality.reason;
    const checks = documentQualityChecks(quality);
    setView((v) => ({
      ...v,
      stage: stageIndex(next.stage),
      prompt: promptFor(mode, next),
      hint: quality.okay ? 'Keep the whole card inside the frame.' : quality.reason,
      chips: [
        { key: 'light', label: checks.light ? 'Good lighting' : 'More light needed', tone: checks.light ? 'ok' : 'warn' },
        { key: 'glare', label: checks.glare ? 'Low glare' : 'Reduce glare', tone: checks.glare ? 'ok' : 'warn' },
        { key: 'sharp', label: checks.sharp ? 'Text sharp' : 'Hold steady', tone: checks.sharp ? 'ok' : 'warn' },
      ],
    }));
    return next.stage === 'complete';
  }, []);

  /** One face / hold-ID frame: lighting, then the up-down head challenge. */
  const faceFrame = useCallback((mode: 'face' | 'hold', video: HTMLVideoElement, canvas: HTMLCanvasElement) => {
    const model = modelRef.current;
    if (!model) throw new Error('Face tracker not loaded');
    const result = model.detectForVideo(video, performance.now());
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) throw new Error('2D canvas unavailable');
    canvas.width = 96;
    canvas.height = 72;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const light = analyzeLighting(ctx.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height);
    const lightProblem = lightingIssue(light);
    // In the hold step the small portrait printed on the card may count as a
    // second face; guide the LARGEST face only (same rule as HoldIdFaceScan).
    const pitch = mode === 'hold' ? observeHolderPitch(result) : observePitch(result);
    // Poor light blocks progress: the seller is asked to fix it rather than
    // submitting a dark photo that the face comparison cannot use.
    const next = advanceChallenge(motionRef.current ?? newMotionChallenge('up'), lightProblem ? null : pitch, performance.now());
    motionRef.current = next;
    const faceIssue = pitch === null
      ? (mode === 'hold'
        ? 'Keep your face inside the oval and the card a little away from it.'
        : 'Keep exactly one face inside the oval; move a little closer.')
      : '';
    lastIssueRef.current = lightProblem || faceIssue;
    // Advisory only: a second, smaller face usually means the card portrait
    // is visible. It never blocks capture, because a small printed portrait
    // is often not detected; the worker and the reviewer check the card.
    const cardSeen = mode === 'hold' && pitch !== null && result.faceLandmarks.length === 2;
    setView((v) => ({
      ...v,
      stage: stageIndex(next.stage),
      prompt: promptFor(mode, next),
      hint: lightProblem || faceIssue || 'Hold the position steady.',
      chips: [
        { key: 'face', label: pitch === null ? 'Center your face' : 'Face in frame', tone: pitch === null ? 'warn' : 'ok' },
        ...(mode === 'hold'
          ? [{ key: 'card', label: cardSeen ? 'Card photo seen' : 'Show the card photo', tone: cardSeen ? 'ok' as const : 'idle' as const }]
          : []),
        { key: 'light', label: lightProblem ? (light.tooDark ? 'More light needed' : 'Too bright') : 'Good lighting', tone: lightProblem ? 'warn' : 'ok' },
        { key: 'glare', label: light.glareHigh ? 'Some glare' : 'Low glare', tone: light.glareHigh ? 'warn' : 'ok' },
      ],
    }));
    return next.stage === 'complete';
  }, []);

  const tick = useCallback((session: number) => {
    if (session !== sessionRef.current || !mountedRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const mode = modeRef.current;
    if (!video || !canvas || !mode || !streamRef.current) return;
    if (performance.now() - startedRef.current > TIMEOUT_MS[mode]) {
      // Stay on this step and tell the seller WHY it did not pass.
      fail(`Step not completed. ${lastIssueRef.current || DEFAULT_ISSUE[mode]} Then try again.`);
      return;
    }
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.currentTime !== lastVideoTimeRef.current) {
      lastVideoTimeRef.current = video.currentTime;
      let done = false;
      try {
        done = isCard(mode) ? cardFrame(mode, video, canvas) : faceFrame(mode, video, canvas);
      } catch {
        fail('Camera tracking stopped. Please try again; your other photos are unchanged.');
        return;
      }
      if (done) {
        capture(mode);
        return;
      }
    }
    timerRef.current = setTimeout(() => tick(session), isCard(mode) ? CARD_TICK_MS : FACE_TICK_MS);
  }, [capture, cardFrame, faceFrame, fail]);

  const start = useCallback(async (mode: CaptureStep) => {
    if (disabledRef.current) return;
    halt();
    sessionRef.current += 1;
    const session = sessionRef.current;
    modeRef.current = mode;
    lastIssueRef.current = '';
    docRef.current = null;
    motionRef.current = null;
    setView((v) => ({
      ...IDLE_VIEW,
      aspect: v.aspect,
      mode,
      status: 'loading',
      chips: initialChips(mode),
    }));
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      fail('Live scanning needs a camera and HTTPS (localhost also works).');
      return;
    }
    try {
      if (!isCard(mode) && !modelRef.current) {
        // Lazy-loaded only for the face steps, and kept for the next step.
        const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision');
        const resolver = await FilesetResolver.forVisionTasks(WASM);
        const model = await FaceLandmarker.createFromOptions(resolver, {
          baseOptions: { modelAssetPath: MODEL, delegate: 'CPU' },
          runningMode: 'VIDEO',
          numFaces: 2,
          outputFacialTransformationMatrixes: true,
        });
        if (!mountedRef.current || modelRef.current) model.close();
        else modelRef.current = model;
      }
      if (session !== sessionRef.current || disabledRef.current || !mountedRef.current) return;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: constraints(mode) });
      if (session !== sessionRef.current || disabledRef.current || !mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) throw new Error('Camera preview unavailable');
      video.srcObject = stream;
      await video.play();
      if (session !== sessionRef.current) return;
      const aspect = video.videoWidth && video.videoHeight ? video.videoWidth / video.videoHeight : DEFAULT_ASPECT;
      // The movement direction is random per attempt. This is a local
      // usability challenge, not a server-signed proof of a live person.
      const coin = (crypto.getRandomValues(new Uint8Array(1))[0] ?? 0) % 2 === 1;
      let challenge: DocumentChallenge | MotionChallenge;
      if (isCard(mode)) {
        docRef.current = newDocumentChallenge(mode, coin ? 'left' : 'right');
        challenge = docRef.current;
      } else {
        motionRef.current = newMotionChallenge(coin ? 'up' : 'down');
        challenge = motionRef.current;
      }
      lastVideoTimeRef.current = -1;
      startedRef.current = performance.now();
      setView((v) => ({ ...v, status: 'active', aspect, stage: 0, prompt: promptFor(mode, challenge) }));
      timerRef.current = setTimeout(() => tick(session), isCard(mode) ? CARD_TICK_MS : FACE_TICK_MS);
    } catch {
      if (session !== sessionRef.current) return;
      fail(isCard(mode)
        ? 'Webcam unavailable. Check camera permission and try again; no gallery upload is accepted.'
        : 'Camera or face tracker unavailable. Check camera permission and try again.');
    }
  }, [fail, halt, tick]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      sessionRef.current += 1;
      halt();
      modelRef.current?.close();
      modelRef.current = null;
    };
  }, [halt]);

  useEffect(() => {
    // Withdrawing consent (or uploading) must switch the camera off at once.
    if (disabled && streamRef.current) stop();
  }, [disabled, stop]);

  return { videoRef, canvasRef, view, start, stop };
}
