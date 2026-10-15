/** Regression coverage and test support for spec editor.test. */
import { describe, expect, it } from 'vitest';
import {
  acceptDetected,
  addSpec,
  createEditor,
  editForm,
  editSpec,
  removeSpec,
  replaceContent,
  specFeedback,
  undoContent,
} from './spec-editor';

const form = {
  title: 'Samsung S21+',
  category: 'mobiles',
  description: '',
  price: '50000',
  specs: [] as { key: string; value: string }[],
};
const start = () => createEditor({ ...form });
const typeText = (s: ReturnType<typeof start>, description: string) =>
  editForm(s, { ...s.details, description });
const value = (s: ReturnType<typeof start>, key: string) =>
  s.details.specs.find((v) => v.key === key)?.value;

describe('automatic specs editor lifecycle', () => {
  it('fills specs immediately, leaves description byte-for-byte intact, and saves current values', () => {
    const text = '8/128, black, non-PTA, back par scratch';
    const s = typeText(start(), text);
    expect(s.details.description).toBe(text);
    expect(value(s, 'Storage')).toBe('128GB');
    expect(Object.fromEntries(s.details.specs.map((r) => [r.key, r.value]))).toHaveProperty(
      'Storage',
      '128GB',
    );
  });
  it('updates/retracts only automatic fields when description is corrected/deleted', () => {
    let s = typeText(start(), '8/128, black');
    s = typeText(s, '8/256, white');
    expect(value(s, 'Storage')).toBe('256GB');
    expect(value(s, 'Colour')).toBe('White');
    s = typeText(s, 'Phone for sale');
    expect(value(s, 'Storage')).toBeUndefined();
  });
  it('retracts an automatic value if the seller makes it ambiguous', () => {
    let s = typeText(start(), '128GB');
    s = typeText(s, '128GB or 256GB');
    expect(value(s, 'Storage')).toBeUndefined();
    expect(specFeedback(s).ambiguous).toContain('Storage');
  });
  it('preserves manual edits, exposes conflict and accepts explicit confirmation', () => {
    let s = typeText(start(), '8/128');
    const i = s.details.specs.findIndex((r) => r.key === 'Storage');
    s = editSpec(s, i, { value: '512GB' });
    s = typeText(s, '8/256');
    expect(value(s, 'Storage')).toBe('512GB');
    expect(specFeedback(s).conflicts).toContainEqual({
      index: i,
      key: 'Storage',
      current: '512GB',
      detected: '256GB',
    });
    s = acceptDetected(s, i);
    expect(value(s, 'Storage')).toBe('256GB');
    expect(specFeedback(s).conflicts).toEqual([]);
  });
  it('does not resurrect an explicitly removed detail while typing or enhancing', () => {
    let s = typeText(start(), '8/128');
    s = removeSpec(
      s,
      s.details.specs.findIndex((r) => r.key === 'Storage'),
    );
    s = typeText(s, '8/256, black');
    expect(value(s, 'Storage')).toBeUndefined();
    s = replaceContent(s, {
      description: 'Good phone, 256GB.',
      specs: [{ key: 'Storage', value: '256GB' }],
    });
    expect(value(s, 'Storage')).toBeUndefined();
  });
  it('preserves manual rename and does not create the old field again', () => {
    let s = typeText(start(), '8/128');
    s = editSpec(
      s,
      s.details.specs.findIndex((r) => r.key === 'Storage'),
      { key: 'My capacity' },
    );
    s = typeText(s, '8/256');
    expect(value(s, 'My capacity')).toBe('128GB');
    expect(value(s, 'Storage')).toBeUndefined();
  });
  it('protects loaded draft fields and recognises alias keys', () => {
    let s = createEditor({ ...form, specs: [{ key: 'ROM', value: '512GB' }] });
    s = typeText(s, '128GB');
    expect(s.details.specs.filter((r) => /ROM|Storage/.test(r.key))).toEqual([
      { key: 'ROM', value: '512GB' },
    ]);
    expect(specFeedback(s).conflicts[0]?.detected).toBe('128GB');
  });
  it('changing category removes old automatic phone fields, keeps manual fields', () => {
    let s = typeText(start(), '8/128, PTA approved');
    s = addSpec(s);
    s = editSpec(s, s.details.specs.length - 1, { key: 'Warranty', value: '1 month' });
    s = editForm(s, {
      ...s.details,
      title: 'Toyota Corolla',
      category: 'vehicles',
      description: '2019 model, 65000 km',
    });
    expect(value(s, 'RAM')).toBeUndefined();
    expect(value(s, 'PTA status')).toBeUndefined();
    expect(value(s, 'Warranty')).toBe('1 month');
    expect(value(s, 'Mileage')).toBe('65000 km');
  });
  it('AI and Undo restore both content and auto ownership, not only visible values', () => {
    const original = typeText(start(), '8/128, black');
    let s = replaceContent(original, {
      description: 'Phone with 8GB RAM and 128GB storage.',
      specs: [{ key: 'Display', value: '6.7 inches' }],
    });
    expect(s.details.description).toMatch(/^Phone with/);
    expect(value(s, 'Storage')).toBe('128GB');
    expect(value(s, 'Display')).toBe('6.7 inches');
    s = undoContent(s);
    expect(s).toEqual(original);
    s = typeText(s, '8/256');
    expect(value(s, 'Storage')).toBe('256GB');
  });
  it('AI cannot overwrite confirmed seller details or remove unreturned faults', () => {
    const initial = createEditor({
      ...form,
      specs: [
        { key: 'Storage', value: '128GB' },
        { key: 'Condition details', value: 'Screen replaced' },
      ],
    });
    const s = replaceContent(initial, {
      description: 'Phone for sale.',
      specs: [{ key: 'ROM', value: '256GB' }],
    });
    expect(s.details.specs).toEqual(initial.details.specs);
  });
  it('does not lose AI researched specs on unrelated typing or price edits', () => {
    let s = replaceContent(start(), {
      description: 'Phone for sale.',
      specs: [{ key: 'Display', value: '6.7 inches' }],
    });
    s = typeText(s, 'Phone for sale. Collection Lahore.');
    s = editForm(s, { ...s.details, price: '45000' });
    expect(value(s, 'Display')).toBe('6.7 inches');
  });
  it('disables Undo after a later manual edit', () => {
    let s = replaceContent(start(), { description: 'Phone for sale.', specs: [] });
    s = typeText(s, 'My newer description');
    expect(s.undo).toBeNull();
    expect(undoContent(s).details.description).toBe('My newer description');
  });
  it('respects the 20-card limit and reports overflow', () => {
    const full = createEditor({
      ...form,
      specs: Array.from({ length: 20 }, (_, i) => ({ key: `Custom ${i}`, value: 'confirmed' })),
    });
    const s = typeText(full, '8/128');
    expect(s.details.specs).toHaveLength(20);
    expect(specFeedback(s).overflow).toBe(true);
    expect(addSpec(s)).toBe(s);
  });
});
