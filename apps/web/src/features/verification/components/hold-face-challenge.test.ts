/** Regression coverage and test support for hold face challenge.test. */
import type { FaceLandmarkerResult } from '@mediapipe/tasks-vision';
import { describe, expect, it } from 'vitest';
import { observeHolderPitch } from './hold-face-challenge';

const landmarks = (width: number) => Array.from({ length: 478 }, (_, i) => ({
  x: i % 2 ? 0.5 - width / 2 : 0.5 + width / 2,
  y: i % 2 ? 0.35 : 0.65,
  z: 0,
  visibility: 1,
}));
const matrix = { rows: 4, columns: 4, data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] };
const result = (...widths: number[]): FaceLandmarkerResult => ({
  faceLandmarks: widths.map(landmarks),
  facialTransformationMatrixes: widths.map(() => matrix),
  faceBlendshapes: [],
});

describe('ID beside face preview', () => {
  it('tracks the largest face when the ID portrait is small', () => {
    expect(observeHolderPitch(result(0.07, 0.32))).toBeCloseTo(0);
    expect(observeHolderPitch(result(0.32, 0.07))).toBeCloseTo(0);
  });
  it('cannot use a card portrait alone as the applicant', () => {
    expect(observeHolderPitch(result(0.07))).toBe(null);
    expect(observeHolderPitch(result())).toBe(null);
  });
  it('rejects two equal-size people and more than two faces', () => {
    expect(observeHolderPitch(result(0.30, 0.29))).toBe(null);
    expect(observeHolderPitch(result(0.3, 0.07, 0.08))).toBe(null);
  });
});
