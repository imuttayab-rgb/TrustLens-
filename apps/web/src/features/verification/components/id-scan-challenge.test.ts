/** Regression coverage and test support for id scan challenge.test. */
import { describe, expect, it } from 'vitest';
import {
  advanceDocumentChallenge,
  analyzeDocumentFrame,
  estimateHorizontalShift,
  newDocumentChallenge,
  type DocumentQuality,
} from './id-scan-challenge';

const W = 48;
const H = 30;

/** Abstract patterned paper; never use a real ID or biometric in tests. */
function texture(shift = 0): Uint8Array {
  const samples = new Uint8Array(W * H);
  for (let y = 0; y < H; y += 1) {
    for (let x = 0; x < W; x += 1) {
      const source = x - shift;
      samples[y * W + x] = source < 0 || source >= W ? 120 :
        (source * 31 + y * 17 + (source * y) % 101) % 160 + 60;
    }
  }
  return samples;
}

function observation(shift = 0, okay = true): DocumentQuality {
  return { okay, reason: okay ? '' : 'Frame is blurred.', brightness: 120, focus: 30, glare: 0, texture: texture(shift) };
}

function frame(width: number, height: number, pixel: (x: number, y: number) => number): Uint8ClampedArray {
  const rgba = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const i = (y * width + x) * 4;
      rgba[i] = rgba[i + 1] = rgba[i + 2] = pixel(x, y);
      rgba[i + 3] = 255;
    }
  }
  return rgba;
}

describe('browser-only ID movement challenge', () => {
  it('rejects empty, dark and blank frames without using real card images', () => {
    expect(analyzeDocumentFrame(new Uint8ClampedArray(0), 0, 0).okay).toBe(false);
    expect(analyzeDocumentFrame(frame(160, 120, () => 10), 160, 120).reason).toContain('light');
    expect(analyzeDocumentFrame(frame(160, 120, () => 125), 160, 120).reason).toContain('sharp');
  });

  it('accepts a well-lit synthetic patterned page and rejects washed-out glare', () => {
    const printed = frame(320, 240, (x, y) => (x * 23 + y * 31) % 19 < 3 ? 60 : 190);
    expect(analyzeDocumentFrame(printed, 320, 240).okay).toBe(true);
    expect(analyzeDocumentFrame(frame(160, 120, () => 255), 160, 120).reason).toContain('glare');
  });

  it('tracks both directions against the neutral sample and rejects unrelated media', () => {
    expect(estimateHorizontalShift(texture(), texture(4))).toBe(4);
    expect(estimateHorizontalShift(texture(), texture(-4))).toBe(-4);
    expect(estimateHorizontalShift(texture(), texture())).toBe(0);
    expect(estimateHorizontalShift(texture(), new Uint8Array(W * H))).toBeNull();
  });

  it('requires sustained center, randomized opposite movements, then center again', () => {
    let state = newDocumentChallenge('front', 'right');
    state = advanceDocumentChallenge(state, observation(), 0);
    state = advanceDocumentChallenge(state, observation(), 700);
    expect(state.stage).toBe('first');
    state = advanceDocumentChallenge(state, observation(4), 800);
    state = advanceDocumentChallenge(state, observation(4), 1000);
    expect(state.stage).toBe('first');
    state = advanceDocumentChallenge(state, observation(4), 1500);
    expect(state.stage).toBe('second');
    state = advanceDocumentChallenge(state, observation(-4), 1600);
    state = advanceDocumentChallenge(state, observation(-4), 2300);
    expect(state.stage).toBe('return');
    state = advanceDocumentChallenge(state, observation(), 2400);
    state = advanceDocumentChallenge(state, observation(), 3100);
    expect(state.stage).toBe('complete');
  });

  it('resets a held movement when focus is lost or the wrong direction is shown', () => {
    let state = newDocumentChallenge('back', 'left');
    state = advanceDocumentChallenge(state, observation(), 0);
    state = advanceDocumentChallenge(state, observation(), 700);
    state = advanceDocumentChallenge(state, observation(-4), 800);
    state = advanceDocumentChallenge(state, observation(4), 1000);
    expect(state.holdSince).toBeNull();
    state = advanceDocumentChallenge(state, observation(-4), 1200);
    state = advanceDocumentChallenge(state, observation(-4, false), 1500);
    expect(state.holdSince).toBeNull();
    expect(state.stage).toBe('first');
  });
});
