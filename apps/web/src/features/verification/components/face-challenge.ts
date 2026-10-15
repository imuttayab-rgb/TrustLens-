/** Reusable UI rendering and interaction component: face challenge. */
import type { FaceLandmarkerResult } from '@mediapipe/tasks-vision';

export type MotionDirection = 'up' | 'down';
export type ChallengeStage = 'center' | 'first' | 'second' | 'return' | 'complete';

export interface MotionChallenge {
  stage: ChallengeStage;
  first: MotionDirection;
  baseline: number | null;
  firstPitch: number | null;
  heldSince: number | null;
  lastSampleAt: number | null;
  /** Collected only while the seller is centered, to reduce baseline jitter. */
  centerSamples: number[];
}

export const HOLD_MS = 650;
const MAX_SAMPLE_GAP_MS = 450;
const PITCH_DELTA_DEGREES = 11;
const CENTER_DELTA_DEGREES = 6;

export function newMotionChallenge(first: MotionDirection): MotionChallenge {
  return {
    stage: 'center',
    first,
    baseline: null,
    firstPitch: null,
    heldSince: null,
    lastSampleAt: null,
    centerSamples: [],
  };
}

export function opposite(direction: MotionDirection): MotionDirection {
  return direction === 'up' ? 'down' : 'up';
}

/**
 * The MediaPipe facial transform is a 4x4 row-major matrix. Its rotation
 * around the horizontal axis gives a relative head pitch. We compare against
 * the same person's initial pose, not a universal 'neutral' face angle.
 *
 * This is client-side motion guidance, NOT server-verified presentation attack
 * detection: a virtual camera, replay, or modified browser can fake it.
 */
export function observePitch(result: FaceLandmarkerResult): number | null {
  if (result.faceLandmarks.length !== 1 || result.facialTransformationMatrixes.length !== 1) {
    return null;
  }
  const landmarks = result.faceLandmarks[0];
  const matrix = result.facialTransformationMatrixes[0];
  if (!landmarks || !matrix || landmarks.length < 400 || matrix.data.length < 16) return null;
  const xs = landmarks.map((point) => point.x);
  const ys = landmarks.map((point) => point.y);
  const width = Math.max(...xs) - Math.min(...xs);
  const height = Math.max(...ys) - Math.min(...ys);
  if (
    width < 0.16 ||
    height < 0.2 ||
    Math.min(...xs) < 0.01 ||
    Math.max(...xs) > 0.99 ||
    Math.min(...ys) < 0.01 ||
    Math.max(...ys) > 0.99
  ) {
    return null;
  }
  const rotation = matrix.data;
  const pitch = (Math.atan2(-rotation[9]!, rotation[10]!) * 180) / Math.PI;
  return Number.isFinite(pitch) ? pitch : null;
}

/** Return a new state so React can render prompts without hidden mutations. */
export function advanceChallenge(
  current: MotionChallenge,
  pitch: number | null,
  now: number,
): MotionChallenge {
  if (current.stage === 'complete') return current;
  if (pitch === null || !Number.isFinite(pitch)) {
    // Losing the only face must break any timed hold; a still photo held up
    // between frames must not inherit the previous person's progress.
    return { ...current, heldSince: null, lastSampleAt: null, centerSamples: [] };
  }
  const last = current.lastSampleAt;
  const heldSince = last === null || now - last > MAX_SAMPLE_GAP_MS ? null : current.heldSince;
  const state = { ...current, lastSampleAt: now, heldSince };

  if (state.stage === 'center') {
    // A short sequence of observations sets the neutral pose; a single noisy
    // frame must not determine the reference angle for both challenges.
    const centerSamples = [...state.centerSamples, pitch].slice(-5);
    if (centerSamples.length < 5) return { ...state, centerSamples };
    const spread = Math.max(...centerSamples) - Math.min(...centerSamples);
    if (spread > CENTER_DELTA_DEGREES) return { ...state, centerSamples: [pitch] };
    return {
      ...state,
      stage: 'first',
      centerSamples: [],
      baseline: centerSamples.reduce((a, b) => a + b, 0) / centerSamples.length,
      heldSince: null,
    };
  }

  const baseline = state.baseline;
  if (baseline === null) return newMotionChallenge(state.first);
  const difference = pitch - baseline;
  // Camera and model coordinate conventions can invert the sign of pitch;
  // demand two clearly opposite movements rather than assuming + means up.
  // The UI prompts up/down, but this geometric check does not independently
  // prove the semantic direction, which is another reason it is not PAD.
  const firstSign = Math.sign((state.firstPitch ?? baseline) - baseline);
  const qualifies =
    state.stage === 'first'
      ? Math.abs(difference) >= PITCH_DELTA_DEGREES
    : state.stage === 'second'
        ? firstSign !== 0 && difference * firstSign <= -PITCH_DELTA_DEGREES
        : Math.abs(difference) <= CENTER_DELTA_DEGREES;
  if (!qualifies) return { ...state, heldSince: null };
  if (state.heldSince === null) return { ...state, heldSince: now };
  if (now - state.heldSince < HOLD_MS) return state;
  if (state.stage === 'first') {
    return { ...state, stage: 'second', firstPitch: pitch, heldSince: null };
  }
  if (state.stage === 'second') return { ...state, stage: 'return', heldSince: null };
  return { ...state, stage: 'complete', heldSince: null };
}
