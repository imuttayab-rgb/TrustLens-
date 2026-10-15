/** Reusable UI rendering and interaction component: spec editor. */
import { detectSpecs, sameValue, specKey, type ProductSpec, type SpecInput } from './auto-specs';

export type SpecForm = SpecInput & { specs: ProductSpec[] };
type Content = Pick<SpecForm, 'description' | 'specs'>;
type Tracking = { automatic: Record<string, string>; suppressed: string[] };
export type Editor<T extends SpecForm> = {
  details: T;
  tracking: Tracking;
  undo: { before: { details: T; tracking: Tracking }; after: Content } | null;
};
export type Conflict = { index: number; key: string; current: string; detected: string };
export const MAX_SPECS = 20;

/** Loaded rows are confirmed facts: no provenance is invented for old listings. */
export function createEditor<T extends SpecForm>(details: T): Editor<T> {
  return { details, tracking: { automatic: {}, suppressed: [] }, undo: null };
}
export function specFeedback<T extends SpecForm>(state: Editor<T>) {
  const detection = detectSpecs(state.details);
  const conflicts: Conflict[] = [];
  for (const found of detection.specs) {
    const index = state.details.specs.findIndex((s) => specKey(s.key) === specKey(found.key));
    const current = state.details.specs[index];
    if (current && !sameValue(current.value, found.value)) {
      conflicts.push({ index, key: current.key, current: current.value, detected: found.value });
    }
  }
  const overflow = detection.specs.some(
    (s) =>
      !state.tracking.suppressed.includes(specKey(s.key)) &&
      !state.details.specs.some((row) => specKey(row.key) === specKey(s.key)),
  );
  return { conflicts, ambiguous: detection.ambiguous, overflow };
}

function sync<T extends SpecForm>(state: Editor<T>, details: T): Editor<T> {
  const detection = detectSpecs(details);
  const candidates = new Map(detection.specs.map((s) => [specKey(s.key), s]));
  const automatic: Record<string, string> = {};
  const rows: ProductSpec[] = [];
  for (const row of details.specs) {
    const key = specKey(row.key);
    if (state.tracking.automatic[key] === row.value) {
      const next = candidates.get(key);
      // Deleted, ambiguous, or no longer relevant facts disappear only if auto-owned.
      if (!next) continue;
      rows.push({ key: row.key, value: next.value });
      automatic[key] = next.value;
    } else rows.push(row);
  }
  for (const row of detection.specs) {
    const key = specKey(row.key);
    if (rows.length >= MAX_SPECS) break;
    if (state.tracking.suppressed.includes(key) || rows.some((s) => specKey(s.key) === key))
      continue;
    rows.push(row);
    automatic[key] = row.value;
  }
  return {
    details: { ...details, specs: rows },
    tracking: { ...state.tracking, automatic },
    undo: null,
  };
}

/** Synchronous, bounded local work: Save and AI always receive the latest extracted facts. */
export function editForm<T extends SpecForm>(state: Editor<T>, details: T): Editor<T> {
  if (
    state.details.title !== details.title ||
    state.details.category !== details.category ||
    state.details.categoryNodeId !== details.categoryNodeId ||
    state.details.description !== details.description
  )
    return sync(state, details);
  return { ...state, details, undo: null };
}
export function addSpec<T extends SpecForm>(state: Editor<T>): Editor<T> {
  if (state.details.specs.length >= MAX_SPECS) return state;
  return {
    ...state,
    details: { ...state.details, specs: [...state.details.specs, { key: '', value: '' }] },
    undo: null,
  };
}
export function editSpec<T extends SpecForm>(
  state: Editor<T>,
  index: number,
  patch: Partial<ProductSpec>,
): Editor<T> {
  const row = state.details.specs[index];
  if (!row) return state;
  const next = { ...row, ...patch };
  const automatic = { ...state.tracking.automatic };
  delete automatic[specKey(row.key)];
  delete automatic[specKey(next.key)];
  const suppressed = new Set(state.tracking.suppressed);
  // A rename must not spawn the old automatic field again on the next keystroke.
  if (specKey(row.key) !== specKey(next.key) && row.key.trim()) suppressed.add(specKey(row.key));
  return {
    details: {
      ...state.details,
      specs: state.details.specs.map((s, i) => (i === index ? next : s)),
    },
    tracking: { automatic, suppressed: [...suppressed] },
    undo: null,
  };
}
export function removeSpec<T extends SpecForm>(state: Editor<T>, index: number): Editor<T> {
  const row = state.details.specs[index];
  if (!row) return state;
  const automatic = { ...state.tracking.automatic };
  delete automatic[specKey(row.key)];
  return {
    details: { ...state.details, specs: state.details.specs.filter((_, i) => i !== index) },
    tracking: {
      automatic,
      suppressed: [...new Set([...state.tracking.suppressed, specKey(row.key)])],
    },
    undo: null,
  };
}
export function acceptDetected<T extends SpecForm>(state: Editor<T>, index: number): Editor<T> {
  const row = state.details.specs[index];
  if (!row) return state;
  const key = specKey(row.key);
  const found = detectSpecs(state.details).specs.find((s) => specKey(s.key) === key);
  if (!found) return state;
  const next = editSpec(state, index, { value: found.value });
  return {
    ...next,
    tracking: { ...next.tracking, automatic: { ...next.tracking.automatic, [key]: found.value } },
  };
}

/** The AI supplements current facts; it cannot erase/override confirmed fields or deletions. */
export function replaceContent<T extends SpecForm>(state: Editor<T>, content: Content): Editor<T> {
  const specs = state.details.specs.map((s) => ({ ...s }));
  for (const row of content.specs) {
    const key = specKey(row.key);
    if (
      !key ||
      !row.value.trim() ||
      row.key.length > 40 ||
      row.value.length > 80 ||
      specs.length >= MAX_SPECS
    )
      continue;
    if (state.tracking.suppressed.includes(key) || specs.some((s) => specKey(s.key) === key))
      continue;
    specs.push({ key: row.key, value: row.value });
  }
  const details = { ...state.details, description: content.description, specs };
  // After a rewrite, preserve only auto ownership whose exact fact remains detectable.
  const detected = new Map(detectSpecs(details).specs.map((s) => [specKey(s.key), s.value]));
  const automatic: Record<string, string> = {};
  for (const row of specs) {
    const key = specKey(row.key);
    if (
      state.tracking.automatic[key] === row.value &&
      sameValue(detected.get(key) ?? '', row.value)
    )
      automatic[key] = row.value;
  }
  return {
    details,
    tracking: { ...state.tracking, automatic },
    undo: {
      before: { details: state.details, tracking: state.tracking },
      after: { description: details.description, specs },
    },
  };
}
export function undoContent<T extends SpecForm>(state: Editor<T>): Editor<T> {
  if (!state.undo) return state;
  return { ...state.undo.before, undo: null };
}
