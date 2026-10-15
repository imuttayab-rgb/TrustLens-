/** Regression coverage and test support for marketplace completion.test. */
import { describe, it, expect } from 'vitest';
import {
  MARKETPLACE_NODES,
  categoryFields,
  categoryGuidance,
  withBrowseLocation,
  browseLocation,
  listingSpecSummary,
  productOptions,
} from '@trustlens/constants';
import { createEditor, editForm, replaceContent } from './spec-editor';
import { readRecovery } from './draft-recovery';
const form = {
  title: 'Samsung S21+',
  category: 'mobiles',
  categoryNodeId: 'mobiles/mobile-phones',
  description: 'Screen replaced. RAM: 8 GB.',
  specs: [],
  condition: 'USED',
  price: '40000',
  negotiable: true,
  showPhone: false,
};
describe('marketplace navigation and reliable category data', () => {
  it('retains only valid location and does not carry tokens or stale areas to a new city', () => {
    const params = new URLSearchParams(
      'city=Lahore&area=Johar+Town&lat=31&lng=74&radius=10&token=secret&q=phone',
    );
    expect(withBrowseLocation('/motors', params)).toBe(
      '/motors?city=Lahore&area=Johar+Town&lat=31&lng=74&radius=10',
    );
    expect(withBrowseLocation('/browse?city=Karachi#results', params)).toBe(
      '/browse?city=Karachi#results',
    );
    expect(browseLocation(new URLSearchParams('lat=999&lng=1&radius=10')).lat).toBeNull();
  });
  it('has category-specific fields, guidance and Urdu coverage for every selectable category', () => {
    for (const n of MARKETPLACE_NODES.filter((n) => n.selectable)) {
      expect(n.schema).not.toBe('general');
      expect(n.labelUr).not.toBe(n.label);
      expect(categoryFields(n.id).length).toBeGreaterThan(0);
      expect(categoryGuidance(n.id)).toBeTruthy();
      expect(categoryGuidance(n.id, true)).toBeTruthy();
    }
  });
  it('does not mix tablet, camera, console and laptop model choices', () => {
    expect(productOptions('mobiles/tablets', 'model', 'Apple')).toContain('iPad 9th generation');
    expect(
      productOptions('mobiles/tablets', 'model', 'Apple').some((x) => x.includes('MacBook')),
    ).toBe(false);
    expect(
      productOptions('electronics-appliances/laptops', 'model', 'Apple').some((x) =>
        x.includes('iPad'),
      ),
    ).toBe(false);
    const camera = MARKETPLACE_NODES.find((n) => n.selectable && n.schema === 'camera')!;
    expect(productOptions(camera.id, 'model', 'Sony')).toContain('A6400');
    expect(productOptions(camera.id, 'model', 'Sony').some((x) => x.includes('PlayStation'))).toBe(
      false,
    );
    expect(productOptions('mobiles/mobile-phones', 'model', 'Unknown')).toEqual([]);
  });
  it('shows only confirmed card facts with explicit property area units', () => {
    expect(listingSpecSummary('property-sale/houses', { area: 5 })).toEqual([]);
    expect(listingSpecSummary('property-sale/houses', { area: 5, area_unit: 'Marla' })).toEqual([
      '5 Marla',
    ]);
    expect(listingSpecSummary('mobiles/mobile-phones', {})).toEqual([]);
    expect(listingSpecSummary('mobiles/mobile-phones', { pta: 'Non-PTA' })).toEqual(['Non-PTA']);
  });
  it('offers farm labels instead of machine hours and does not infer phone RAM', () => {
    const node = 'business-industrial-agriculture/agriculture/seeds';
    expect(categoryFields(node).map((f) => f.key)).toContain('variety');
    expect(categoryFields(node).map((f) => f.key)).not.toContain('hours');
    const data = {
      ...form,
      category: 'business',
      categoryNodeId: node,
      description: 'Variety: Wheat; Quantity: 10; Quantity unit: kg',
    };
    const e = editForm(createEditor({ ...data, description: '' }), data);
    expect(e.details.specs.some((s: { key: string }) => s.key === 'RAM')).toBe(false);
  });
});
describe('recoverable public draft text', () => {
  const now = 100000000;
  const editor = replaceContent(createEditor(form), {
    description: 'Used phone. Screen replaced.',
    specs: [],
  });
  const record = () => ({
    version: 1,
    at: now,
    editor,
    categories: [['mobiles/mobile-phones', editor]],
    dirty: true,
  });
  it('restores exact content and AI Undo from a recovery snapshot', () => {
    expect(readRecovery(JSON.stringify(record()), now)?.editor).toEqual(editor);
  });
  it('rejects expired, future and malformed records without throwing', () => {
    for (const value of [
      null,
      [],
      { ...record(), at: 0 },
      { ...record(), at: now + 60001 },
      { ...record(), categories: [null] },
      { ...record(), editor: { ...editor, tracking: { automatic: null, suppressed: [] } } },
      { ...record(), editor: { ...editor, undo: {} } },
    ])
      expect(readRecovery(JSON.stringify(value), now)).toBeNull();
  });
  it('rejects injected private fields and invalid categories', () => {
    for (const extra of [
      { addressLine: 'private address' },
      { token: 'secret' },
      { categoryNodeId: 'not-a-real-category' },
    ])
      expect(
        readRecovery(
          JSON.stringify({
            ...record(),
            editor: { ...editor, details: { ...editor.details, ...extra } },
          }),
          now,
        ),
      ).toBeNull();
  });
});

import { readDraftRecovery, writeDraftRecovery, removeDraftRecovery, clearDraftRecovery } from '../../../lib/draft-recovery-cache';
it('isolates in-app recovery by account and clears it at logout', () => {
  clearDraftRecovery();
  writeDraftRecovery('user-a:new', 'draft-a');
  expect(readDraftRecovery('user-b:new')).toBeNull();
  expect(readDraftRecovery('user-a:new')).toBe('draft-a');
  removeDraftRecovery('user-a:new');
  expect(readDraftRecovery('user-a:new')).toBeNull();
  writeDraftRecovery('user-b:new', 'draft-b');
  clearDraftRecovery(); expect(readDraftRecovery('user-b:new')).toBeNull();
});
