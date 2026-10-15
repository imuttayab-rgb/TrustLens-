/** Reusable UI rendering and interaction component: id scan challenge. */
export type Side = 'front' | 'back';
export type Direction = 'left' | 'right';
export type Stage = 'center' | 'first' | 'second' | 'return' | 'complete';

export interface DocumentQuality {
  okay: boolean;
  reason: string;
  brightness: number;
  focus: number;
  glare: number;
  /** Small luminance sample of the GUIDE AREA, not a saved biometric/ID image. */
  texture: Uint8Array;
}

export interface DocumentChallenge {
  side: Side;
  first: Direction;
  stage: Stage;
  holdSince: number | null;
  /** Ephemeral neutral-frame texture. It never leaves this browser session. */
  baseline: Uint8Array | null;
}

const GRID_WIDTH = 48;
const GRID_HEIGHT = 30;
const HOLD_MS = 650;
const MIN_MOVE_CELLS = 3;
// Frame-quality limits. Shared by analyzeDocumentFrame (which blocks capture)
// and documentQualityChecks (which drives the on-screen status chips), so the
// chips can never disagree with what actually blocks the scan.
const MIN_LIGHT = 55;
const MAX_LIGHT = 220;
const MAX_GLARE_RATIO = 0.28;
const MIN_EDGE_ENERGY = 18;

export function oppositeDirection(direction: Direction): Direction {
  return direction === 'left' ? 'right' : 'left';
}

export function newDocumentChallenge(side: Side, first: Direction): DocumentChallenge {
  return { side, first, stage: 'center', holdSince: null, baseline: null };
}

/**
 * Use image luminance and a small guide-region grid for light/focus checks.
 * These are UX quality heuristics, NOT evidence of a real or authentic CNIC.
 * Keeping the pure computation separate from camera code permits synthetic tests.
 */
export function analyzeDocumentFrame(
  rgba: Uint8ClampedArray,
  width: number,
  height: number,
): DocumentQuality {
  if (width < 80 || height < 60 || rgba.length < width * height * 4) {
    return { okay: false, reason: 'Camera frame unavailable.', brightness: 0, focus: 0, glare: 0, texture: new Uint8Array(0) };
  }
  const texture = new Uint8Array(GRID_WIDTH * GRID_HEIGHT);
  let light = 0;
  let glare = 0;
  for (let y = 0; y < GRID_HEIGHT; y += 1) {
    for (let x = 0; x < GRID_WIDTH; x += 1) {
      // Crop inside the on-screen 75%-wide / 60%-high alignment guide.
      const sx = Math.floor(width * (0.125 + (x + 0.5) * 0.75 / GRID_WIDTH));
      const sy = Math.floor(height * (0.20 + (y + 0.5) * 0.60 / GRID_HEIGHT));
      const i = (sy * width + sx) * 4;
      const value = Math.round(rgba[i]! * 0.299 + rgba[i + 1]! * 0.587 + rgba[i + 2]! * 0.114);
      texture[y * GRID_WIDTH + x] = value;
      light += value;
      if (value > 248) glare += 1;
    }
  }
  const brightness = light / texture.length;
  const glareRatio = glare / texture.length;
  // An edge-energy estimate rejects blank/defocused frames without including
  // card metadata, OCR, or any guess about whether the physical ID is valid.
  let focus = 0;
  let count = 0;
  for (let y = 1; y < GRID_HEIGHT - 1; y += 1) {
    for (let x = 1; x < GRID_WIDTH - 1; x += 1) {
      const i = y * GRID_WIDTH + x;
      focus += Math.abs(4 * texture[i]! - texture[i - 1]! - texture[i + 1]! - texture[i - GRID_WIDTH]! - texture[i + GRID_WIDTH]!);
      count += 1;
    }
  }
  const edgeEnergy = focus / count;
  const reason =
    brightness < MIN_LIGHT ? 'More light needed — move away from shadows.' :
    brightness > MAX_LIGHT || glareRatio > MAX_GLARE_RATIO ? 'Reduce glare or move the card away from direct light.' :
    edgeEnergy < MIN_EDGE_ENERGY ? 'Move the card slowly until the text looks sharp.' : '';
  return { okay: !reason, reason, brightness, focus: edgeEnergy, glare: glareRatio, texture };
}

/**
 * Pass/fail for each quality check, for the live status chips. Uses the same
 * limits as analyzeDocumentFrame. UX heuristics only, not document authenticity.
 */
export function documentQualityChecks(quality: DocumentQuality): {
  light: boolean;
  glare: boolean;
  sharp: boolean;
} {
  return {
    light: quality.brightness >= MIN_LIGHT,
    glare: quality.brightness <= MAX_LIGHT && quality.glare <= MAX_GLARE_RATIO,
    sharp: quality.focus >= MIN_EDGE_ENERGY,
  };
}

/**
 * Correlate a downsampled neutral frame with the current frame to estimate
 * horizontal card motion. Virtual cameras or an attacker-controlled client
 * can bypass this entirely; it is a local presentation challenge, not PAD.
 * No coordinate/image/video is submitted as a proof to the backend.
 */
export function estimateHorizontalShift(reference: Uint8Array, current: Uint8Array): number | null {
  if (reference.length !== GRID_WIDTH * GRID_HEIGHT || current.length !== reference.length) return null;
  let bestError = Infinity;
  let zeroError = Infinity;
  let bestShift = 0;
  for (let shift = -7; shift <= 7; shift += 1) {
    let difference = 0;
    let count = 0;
    // Compare a common central window so every shift has the same sample count.
    for (let y = 3; y < GRID_HEIGHT - 3; y += 2) {
      for (let x = 8; x < GRID_WIDTH - 8; x += 1) {
        difference += Math.abs(current[y * GRID_WIDTH + x]! - reference[y * GRID_WIDTH + x - shift]!);
        count += 1;
      }
    }
    const error = difference / count;
    if (shift === 0) zeroError = error;
    if (error < bestError) {
      bestError = error;
      bestShift = shift;
    }
  }
  // Quality/confidence gate: lighting changes or an unrelated scene should
  // not count as valid movement just because one offset happens to fit best.
  if (bestError > 42 || (bestShift !== 0 && bestError > zeroError * 0.9)) return null;
  return bestShift;
}

export function advanceDocumentChallenge(
  state: DocumentChallenge,
  quality: DocumentQuality,
  now: number,
): DocumentChallenge {
  if (state.stage === 'complete') return state;
  if (!quality.okay) return { ...state, holdSince: null };
  if (state.stage === 'center') {
    if (!state.baseline) return { ...state, baseline: quality.texture, holdSince: now };
    const shift = estimateHorizontalShift(state.baseline, quality.texture);
    if (shift === null || Math.abs(shift) > 1) {
      return { ...state, baseline: quality.texture, holdSince: now };
    }
    if (now - (state.holdSince ?? now) >= HOLD_MS) {
      return { ...state, stage: 'first', holdSince: null };
    }
    return state;
  }
  const shift = estimateHorizontalShift(state.baseline!, quality.texture);
  const required: Direction | null = state.stage === 'first'
    ? state.first
    : state.stage === 'second' ? oppositeDirection(state.first) : null;
  const matches = state.stage === 'return'
    ? shift !== null && Math.abs(shift) <= 1
    : required === 'right' ? shift !== null && shift >= MIN_MOVE_CELLS
    : shift !== null && shift <= -MIN_MOVE_CELLS;
  if (!matches) return { ...state, holdSince: null };
  if (state.holdSince === null) return { ...state, holdSince: now };
  if (now - state.holdSince < HOLD_MS) return state;
  return {
    ...state,
    stage: state.stage === 'first' ? 'second' : state.stage === 'second' ? 'return' : 'complete',
    holdSince: null,
  };
}
