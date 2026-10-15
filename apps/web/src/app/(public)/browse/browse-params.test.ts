/** Regression coverage and test support for browse params.test. */
import { describe, expect, it } from 'vitest';
import { nextBrowseHref, pageFromParam, priceFromInput, priceRangeError } from './browse-params';

describe('marketplace category URL synchronization', () => {
  it('replaces a header-selected category from the sidebar and resets the page', () => {
    const next = nextBrowseHref('category=electronics&q=phone&city=Lahore&minPrice=100&page=4', {
      category: 'mobiles',
    });
    expect(next).toBe('/browse?category=mobiles&q=phone&city=Lahore&minPrice=100');
  });

  it('allows All categories from the sidebar without discarding other filters', () => {
    expect(
      nextBrowseHref('category=vehicles&sort=price_asc&verified=1&page=2', { category: null }),
    ).toBe('/browse?sort=price_asc&verified=1');
  });

  it('does not discard an applied category when a separate filter is updated', () => {
    expect(nextBrowseHref('category=fashion&city=Karachi', { minPrice: '500' })).toBe(
      '/browse?category=fashion&city=Karachi&minPrice=500',
    );
  });

  it('retains pagination when a non-filter display option changes', () => {
    expect(nextBrowseHref('category=services&page=3', { view: 'list' }, false)).toBe(
      '/browse?category=services&page=3&view=list',
    );
  });

  it('returns to page one when sorting changes without losing search constraints', () => {
    expect(
      nextBrowseHref('q=phone&city=Lahore&maxPrice=40000&page=4&view=list', { sort: 'price_asc' }),
    ).toBe('/browse?q=phone&city=Lahore&maxPrice=40000&view=list&sort=price_asc');
  });

  it('applies a new city and its chosen area together', () => {
    expect(
      nextBrowseHref('city=Karachi&area=Clifton&page=2', { city: 'Lahore', area: 'DHA' }),
    ).toBe('/browse?city=Lahore&area=DHA');
  });
});

describe('buyer-entered and shared-link price constraints', () => {
  it('keeps zero and accepts properly grouped Pakistan prices', () => {
    expect(priceFromInput('0')).toBe(0);
    expect(priceFromInput(' 40,000 ')).toBe(40000);
    expect(priceFromInput('1250.50')).toBe(1250.5);
    expect(priceRangeError('0', '40,000')).toBeNull();
  });

  it('rejects malformed prices instead of silently treating them as valid budgets', () => {
    for (const input of ['-1', 'Infinity', 'NaN', '0x100', '4,0', '12.345', '1e4']) {
      expect(priceFromInput(input)).toBeNull();
      expect(priceRangeError(null, input)).not.toBeNull();
    }
  });

  it('does not turn an open-ended range into a zero budget', () => {
    expect(priceFromInput(null)).toBeNull();
    expect(priceFromInput(' ')).toBeNull();
    expect(priceRangeError('', '40000')).toBeNull();
  });

  it('blocks inverted ranges and accepts an exact price', () => {
    expect(priceRangeError('50000', '40000')).not.toBeNull();
    expect(priceRangeError('40000', '40000')).toBeNull();
  });

  it('does not send fractional, nonfinite or overflowing page offsets', () => {
    for (const input of ['0', '-3', '2.5', 'Infinity', '9007199254740991', 'abc', null]) {
      expect(pageFromParam(input)).toBe(1);
    }
    expect(pageFromParam('3')).toBe(3);
  });
});
