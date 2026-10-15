/**
 * Whole-frame lighting estimate for the live FACE and HOLD-ID steps.
 *
 * The CNIC steps already use `analyzeDocumentFrame` (guide-region light, glare
 * and focus). Face steps had no light measurement, so a seller in a dark room
 * only saw "keep one face in frame". This helper gives them a concrete reason
 * and lets the wizard pause the challenge until the light is usable.
 *
 * These are UX quality heuristics computed on a tiny downsampled frame in the
 * browser. They are NOT liveness, anti-spoofing or identity evidence, and no
 * pixel data leaves the device because of them.
 */
export interface LightingSample {
  /** Mean luminance, 0 (black) to 255 (white). */
  brightness: number;
  /** Share of sampled pixels that are blown out (near-white). */
  glare: number;
  tooDark: boolean;
  tooBright: boolean;
  /** Advisory only: a bright window behind the seller is common and allowed. */
  glareHigh: boolean;
}

// Deliberately wider than the CNIC thresholds (55-220): a face is far more
// tolerant of light than small printed card text is.
const MIN_BRIGHTNESS = 45;
const MAX_BRIGHTNESS = 225;
const GLARE_LEVEL = 248;
const GLARE_RATIO = 0.2;
// ~4,800 samples is plenty for a mean and keeps the per-frame cost tiny.
const TARGET_SAMPLES = 4_800;

export function analyzeLighting(
  rgba: Uint8ClampedArray,
  width: number,
  height: number,
): LightingSample {
  const pixels = width * height;
  if (width < 8 || height < 8 || rgba.length < pixels * 4) {
    // No usable frame: treat as dark so the challenge cannot advance on it.
    return { brightness: 0, glare: 0, tooDark: true, tooBright: false, glareHigh: false };
  }
  const step = Math.max(1, Math.floor(Math.sqrt(pixels / TARGET_SAMPLES)));
  let light = 0;
  let blown = 0;
  let count = 0;
  for (let y = 0; y < height; y += step) {
    for (let x = 0; x < width; x += step) {
      const i = (y * width + x) * 4;
      const value = rgba[i]! * 0.299 + rgba[i + 1]! * 0.587 + rgba[i + 2]! * 0.114;
      light += value;
      if (value > GLARE_LEVEL) blown += 1;
      count += 1;
    }
  }
  const brightness = light / count;
  const glare = blown / count;
  return {
    brightness,
    glare,
    tooDark: brightness < MIN_BRIGHTNESS,
    tooBright: brightness > MAX_BRIGHTNESS,
    glareHigh: glare > GLARE_RATIO,
  };
}

/** The retry reason shown to the seller, or '' when the light is usable. */
export function lightingIssue(sample: LightingSample): string {
  if (sample.tooDark) return 'More light needed — face a window or a lamp.';
  if (sample.tooBright) return 'Too bright — move away from direct light.';
  return '';
}
