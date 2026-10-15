/**
 * Step order for the live identity wizard.
 *
 * Kept free of React so the "what comes next" rules can be unit-tested. The
 * wizard only moves forward after a step's live capture succeeds; a failed or
 * timed-out scan keeps the seller on the same step with a retry reason.
 */
export type CaptureStep = 'front' | 'back' | 'face' | 'hold';
export type StepId = 'consent' | CaptureStep | 'submit';
export type StepState = 'complete' | 'active' | 'pending';

export interface WizardStep {
  id: StepId;
  label: string;
}

export type Captured = Record<CaptureStep, boolean>;

/**
 * The hold-ID step exists only when NEXT_PUBLIC_HOLD_ID_SCAN is on, because
 * the API then REQUIRES that fourth image. Without it the wizard has 5 steps.
 */
export function buildSteps(holdEnabled: boolean): WizardStep[] {
  return [
    { id: 'consent', label: 'Consent' },
    { id: 'front', label: 'CNIC front' },
    { id: 'back', label: 'CNIC back' },
    { id: 'face', label: 'Face scan' },
    ...(holdEnabled ? [{ id: 'hold' as const, label: 'Hold ID' }] : []),
    { id: 'submit', label: 'Submit' },
  ];
}

export function isCaptureStep(id: StepId): id is CaptureStep {
  return id === 'front' || id === 'back' || id === 'face' || id === 'hold';
}

/** Capture steps in this wizard, in order (excludes consent and submit). */
export function captureSteps(steps: WizardStep[]): CaptureStep[] {
  return steps.map((step) => step.id).filter(isCaptureStep);
}

/**
 * After `from` is captured, go to the next step that still has no photo.
 * If the seller went back to retake an earlier photo, this skips steps that
 * are already done instead of making them redo everything. Any missing step
 * earlier in the list is caught before Submit is offered.
 */
export function nextStepAfter(steps: WizardStep[], from: StepId, captured: Captured): StepId {
  const order = captureSteps(steps);
  const start = steps.findIndex((step) => step.id === from);
  const later = order.filter((id) => steps.findIndex((s) => s.id === id) > start);
  const missingLater = later.find((id) => !captured[id]);
  if (missingLater) return missingLater;
  const missingAny = order.find((id) => !captured[id]);
  return missingAny ?? 'submit';
}

/** True only when every capture step this wizard needs has a photo. */
export function allCaptured(steps: WizardStep[], captured: Captured): boolean {
  return captureSteps(steps).every((id) => captured[id]);
}

export function stepState(
  step: StepId,
  current: StepId,
  captured: Captured,
  submitted: boolean,
): StepState {
  if (step === current && !(step === 'submit' && submitted)) return 'active';
  if (step === 'consent') return current === 'consent' ? 'active' : 'complete';
  if (step === 'submit') return submitted ? 'complete' : 'pending';
  // A step is "complete" only when its photo really exists, so a step that
  // was skipped or cleared can never be shown as done.
  return captured[step] ? 'complete' : 'pending';
}
