/** Regression coverage and test support for LiveVerificationWizard.test. */
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { documentQualityChecks, type DocumentQuality } from './id-scan-challenge';
import { analyzeLighting, lightingIssue } from './scan-lighting';
import { initialChips, promptFor } from './use-live-capture';
import { allCaptured, buildSteps, nextStepAfter, stepState, type Captured } from './wizard-steps';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
vi.mock('@tanstack/react-query', () => ({ useQueryClient: () => ({ invalidateQueries: vi.fn() }) }));
vi.mock('../hooks/use-job-status', () => ({ useJobStatus: () => ({ data: undefined }) }));
vi.mock('@/lib/api/client', () => ({ api: { POST: vi.fn() } }));
vi.mock('@/lib/upload', () => ({ uploadFile: vi.fn() }));
vi.mock('@/lib/api/query-keys', () => ({ qk: { verification: { status: ['verification', 'status'] } } }));
vi.mock('@/lib/forms/use-api-form', () => ({}));

const NONE: Captured = { front: false, back: false, face: false, hold: false };

function frame(value: number, width = 64, height = 48): Uint8ClampedArray {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < data.length; i += 4) {
    data[i] = value;
    data[i + 1] = value;
    data[i + 2] = value;
    data[i + 3] = 255;
  }
  return data;
}

describe('wizard step order', () => {
  it('runs CNIC front -> back -> face -> hold ID -> submit when hold-ID is on', () => {
    const steps = buildSteps(true);
    expect(steps.map((s) => s.id)).toEqual(['consent', 'front', 'back', 'face', 'hold', 'submit']);
    expect(nextStepAfter(steps, 'consent', NONE)).toBe('front');
    expect(nextStepAfter(steps, 'front', { ...NONE, front: true })).toBe('back');
    expect(nextStepAfter(steps, 'back', { ...NONE, front: true, back: true })).toBe('face');
    expect(nextStepAfter(steps, 'face', { front: true, back: true, face: true, hold: false })).toBe('hold');
    expect(nextStepAfter(steps, 'hold', { front: true, back: true, face: true, hold: true })).toBe('submit');
  });

  it('has five steps and no hold-ID step when that flag is off', () => {
    const steps = buildSteps(false);
    expect(steps.map((s) => s.id)).toEqual(['consent', 'front', 'back', 'face', 'submit']);
    expect(nextStepAfter(steps, 'face', { front: true, back: true, face: true, hold: false })).toBe('submit');
    expect(allCaptured(steps, { front: true, back: true, face: true, hold: false })).toBe(true);
  });

  it('after a retake, skips steps that are already done', () => {
    const steps = buildSteps(true);
    const all = { front: true, back: true, face: true, hold: true };
    expect(nextStepAfter(steps, 'front', all)).toBe('submit');
    // Retaking the back while the face is still missing goes to the face.
    expect(nextStepAfter(steps, 'back', { ...all, face: false })).toBe('face');
  });

  it('never offers submit while an earlier step is missing', () => {
    const steps = buildSteps(true);
    expect(nextStepAfter(steps, 'hold', { front: false, back: true, face: true, hold: true })).toBe('front');
    expect(allCaptured(steps, { front: false, back: true, face: true, hold: true })).toBe(false);
  });

  it('shows a capture step as complete only when its photo exists', () => {
    expect(stepState('front', 'back', { ...NONE, front: true }, false)).toBe('complete');
    expect(stepState('face', 'back', NONE, false)).toBe('pending');
    expect(stepState('back', 'back', NONE, false)).toBe('active');
    expect(stepState('consent', 'front', NONE, false)).toBe('complete');
    expect(stepState('submit', 'submit', NONE, true)).toBe('complete');
  });
});

describe('face-step lighting check', () => {
  it('asks for more light in a dark frame', () => {
    const dark = analyzeLighting(frame(20), 64, 48);
    expect(dark.tooDark).toBe(true);
    expect(lightingIssue(dark)).toContain('More light');
  });

  it('flags an overexposed frame', () => {
    const bright = analyzeLighting(frame(252), 64, 48);
    expect(bright.tooBright).toBe(true);
    expect(bright.glareHigh).toBe(true);
    expect(lightingIssue(bright)).toContain('Too bright');
  });

  it('accepts normal light', () => {
    const ok = analyzeLighting(frame(130), 64, 48);
    expect(lightingIssue(ok)).toBe('');
  });

  it('treats a missing frame as unusable instead of passing it', () => {
    expect(analyzeLighting(new Uint8ClampedArray(0), 0, 0).tooDark).toBe(true);
  });
});

describe('CNIC quality chips use the same limits as the capture gate', () => {
  const base: DocumentQuality = { okay: true, reason: '', brightness: 120, focus: 30, glare: 0.01, texture: new Uint8Array(0) };
  it('passes a good frame', () => {
    expect(documentQualityChecks(base)).toEqual({ light: true, glare: true, sharp: true });
  });
  it('fails each check on its own threshold', () => {
    expect(documentQualityChecks({ ...base, brightness: 40 }).light).toBe(false);
    expect(documentQualityChecks({ ...base, glare: 0.4 }).glare).toBe(false);
    expect(documentQualityChecks({ ...base, focus: 5 }).sharp).toBe(false);
  });
});

describe('live capture copy', () => {
  it('only shows chips for checks the code really performs', () => {
    expect(initialChips('front').map((c) => c.key)).toEqual(['light', 'glare', 'sharp']);
    expect(initialChips('face').map((c) => c.key)).toEqual(['face', 'light', 'glare']);
    expect(initialChips('hold').map((c) => c.key)).toEqual(['face', 'card', 'light', 'glare']);
  });

  it('uses the approved hold-ID instruction', () => {
    expect(promptFor('hold', { stage: 'center', first: 'up', baseline: null, firstPitch: null, heldSince: null, lastSampleAt: null, centerSamples: [] }))
      .toBe('Hold the card next to your face and keep still');
  });
});

describe('LiveVerificationWizard first render', () => {
  it('starts at consent with the camera off and no gallery upload', async () => {
    const { LiveVerificationWizard } = await import('./LiveVerificationWizard');
    const html = renderToStaticMarkup(createElement(LiveVerificationWizard, { holdEnabled: true }));
    expect(html).toContain('Verify your identity');
    expect(html).toContain('Step 1 of 6');
    expect(html).toContain('CNIC front');
    expect(html).toContain('Hold ID');
    expect(html).toContain('What happens after you submit');
    expect(html).toContain('Deleted 90 days after a decision');
    expect(html).toContain('Your camera turns on only after you agree.');
    expect(html).not.toContain('type="file"');
    // Continue stays disabled until consent is given.
    expect(html).toMatch(/<button[^>]*disabled[^>]*>Agree and continue/);
  });

  it('makes no authenticity, PAD or NADRA claims', async () => {
    const { LiveVerificationWizard } = await import('./LiveVerificationWizard');
    const html = renderToStaticMarkup(createElement(LiveVerificationWizard, { holdEnabled: true }));
    expect(html).not.toMatch(/authenticity|presentation-attack|not stored/i);
    expect(html).toContain('not a NADRA record check');
  });
});
