/** Regression coverage and test support for category flow.test. */
import { describe, it, expect } from 'vitest';
import { categoryFields, categoryFieldErrors, categoryNode } from '@trustlens/constants';
import {
  createEditor,
  editForm,
  editSpec,
  replaceContent,
  specFeedback,
  undoContent,
} from './spec-editor';
import { missingForPublish } from './post-ad-helpers';
const form = {
  title: 'Samsung S21+',
  category: 'mobiles',
  categoryNodeId: 'mobiles/mobile-phones',
  description: 'RAM: 8GB; Storage: 128GB; screen replaced',
  specs: [] as { key: string; value: string }[],
};
describe('category-aware posting without weakening existing flows', () => {
  it('detects cards before any AI action, keeps confirmed conflicts, and undoes rewrite', () => {
    let e = editForm(createEditor({ ...form, description: '' }), form);
    expect(e.details.specs.find((s) => s.key === 'RAM')?.value).toBe('8GB');
    const i = e.details.specs.findIndex((s) => s.key === 'RAM');
    e = editSpec(e, i, { value: '12GB' });
    expect(specFeedback(e).conflicts.length).toBeGreaterThan(0);
    const changed = replaceContent(e, {
      description: 'Screen replaced. No charger.',
      specs: [{ key: 'RAM', value: '16GB' }],
    });
    expect(changed.details.specs.find((s) => s.key === 'RAM')?.value).toBe('12GB');
    expect(undoContent(changed).details).toEqual(e.details);
  });
  it('uses skincare fields instead of phone labels and never supplies unknown expiry', () => {
    const input = {
      ...form,
      category: 'fashion',
      categoryNodeId: 'fashion-beauty/skincare',
      description: 'Brand: Test; Quantity: 30; Quantity unit: ml; Seal / use status: Opened',
    };
    const e = editForm(createEditor({ ...input, description: '' }), input);
    expect(categoryFields(input.categoryNodeId).some((f) => f.key === 'expiry')).toBe(true);
    expect(categoryFields(input.categoryNodeId).some((f) => f.key === 'ram')).toBe(false);
    expect(e.details.specs.some((s) => s.key === 'Expiry date')).toBe(false);
    expect(e.details.specs.find((s) => s.key === 'Quantity')?.value).toBe('30');
  });
  it('validates real dates and bounds, retaining unknown facts as blank', () => {
    expect(
      categoryFieldErrors('fashion-beauty/skincare', [{ key: 'Expiry date', value: '2026-02-30' }]),
    ).toHaveLength(1);
    expect(
      categoryFieldErrors('mobiles/mobile-phones', [{ key: 'Battery health', value: '110%' }]),
    ).toHaveLength(1);
    expect(categoryFieldErrors('fashion-beauty/skincare', [])).toEqual([]);
  });
  it('keeps physical media requirements and explicitly scopes virtual categories', () => {
    const input = {
      photoCount: 0,
      hasVideo: false,
      latitude: null,
      longitude: null,
      addressLine: null,
    };
    expect(missingForPublish(input)).toEqual(['photo', 'video', 'location']);
    expect(missingForPublish({ ...input, policy: 'virtual' })).toEqual([]);
    expect(categoryNode('mobiles/mobile-phones')?.policy).toBe('physical');
  });
});
