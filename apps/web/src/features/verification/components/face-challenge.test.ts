/** Regression coverage and test support for face challenge.test. */
import type { FaceLandmarkerResult } from '@mediapipe/tasks-vision';
import { describe, expect, it } from 'vitest';
import { advanceChallenge, newMotionChallenge, observePitch } from './face-challenge';

function centered(now = 0) {
  let state = newMotionChallenge('up');
  for (let n = 0; n < 5; n += 1) state = advanceChallenge(state, 0, now + n * 100);
  return state;
}

describe('live camera challenge', () => {
  it('requires up AND down, each held across multiple live frames, then centered', () => {
    let state = centered();
    expect(state.stage).toBe('first');
    state = advanceChallenge(state, 2, 500); // too small to count as a motion
    expect(state.stage).toBe('first');
    state = advanceChallenge(state, 15, 600);
    state = advanceChallenge(state, 15, 1300); // a long sampling gap breaks the hold
    expect(state.stage).toBe('first');
    for (let t = 1400; t <= 2100; t += 100) state = advanceChallenge(state, 15, t);
    expect(state.stage).toBe('second');
    state = advanceChallenge(state, 15, 2150); // same direction cannot count twice
    expect(state.stage).toBe('second');
    for (let t = 2200; t <= 2900; t += 100) state = advanceChallenge(state, -15, t);
    expect(state.stage).toBe('return');
    for (let t = 3000; t <= 3700; t += 100) state = advanceChallenge(state, 0, t);
    expect(state.stage).toBe('complete');
  });

  it('losing the face resets a hold but does not mark the challenge complete', () => {
    let state = centered();
    state = advanceChallenge(state, 16, 500);
    state = advanceChallenge(state, null, 600);
    expect(state.heldSince).toBe(null);
    state = advanceChallenge(state, 16, 1400);
    expect(state.stage).toBe('first');
  });

  it('requires five stable neutral frames for calibration', () => {
    let state = newMotionChallenge('down');
    for (const [index, pitch] of [0, 3, 17, 0, 1].entries()) {
      state = advanceChallenge(state, pitch, index * 100);
    }
    expect(state.stage).toBe('center');
    for (let i = 5; i < 10; i += 1) state = advanceChallenge(state, 0, i * 100);
    expect(state.stage).toBe('first');
    expect(state.first).toBe('down');
  });

  it('accepts a reversed model pitch sign if the second pose is opposite', () => {
    let state = centered();
    for (let t = 500; t <= 1200; t += 100) state = advanceChallenge(state, -14, t);
    expect(state.stage).toBe('second');
    for (let t = 1300; t <= 2000; t += 100) state = advanceChallenge(state, 14, t);
    expect(state.stage).toBe('return');
  });
});

describe('MediaPipe frame validation', () => {
  const landmarks = Array.from({ length: 478 }, (_, i) => ({
    x: i % 2 ? 0.4 : 0.6,
    y: i % 2 ? 0.35 : 0.65,
    z: 0,
    visibility: 1,
  }));
  const transform = { rows: 4, columns: 4, data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] };

  it('rejects zero or multiple faces and accepts one in-frame face', () => {
    const result = {
      faceLandmarks: [landmarks],
      facialTransformationMatrixes: [transform],
      faceBlendshapes: [],
    };
    expect(observePitch(result as FaceLandmarkerResult)).toBeCloseTo(0);
    expect(observePitch({ ...result, faceLandmarks: [] })).toBe(null);
    expect(observePitch({ ...result, faceLandmarks: [landmarks, landmarks] })).toBe(null);
  });
});
