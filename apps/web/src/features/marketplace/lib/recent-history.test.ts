/** Prevent private listing details from being persisted in browser history. */
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { HISTORY_KEY, clearRecentlyViewed, readHistory, recordHistory } from './recent-history';
const id = '10000000-0000-0000-0000-000000000001';
let values: Map<string, string>;
beforeEach(() => {
  values = new Map();
  vi.stubGlobal('window', {
    localStorage: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    },
    dispatchEvent: vi.fn(),
  });
});
afterEach(() => vi.unstubAllGlobals());
it('migrates old history without retaining names, phone, location or photos', () => {
  values.set(
    HISTORY_KEY,
    JSON.stringify([
      { id, sellerDisplayName: 'PRIVATE', phone: 'PRIVATE', latitude: 22, imageUrl: 'PRIVATE' },
    ]),
  );
  expect(readHistory()).toHaveLength(1);
  expect(values.get(HISTORY_KEY)).not.toMatch(/PRIVATE|latitude|imageUrl/);
});
it('expires old entries and rejects invalid identifiers', () => {
  values.set(
    HISTORY_KEY,
    JSON.stringify([
      { id, viewedAt: 1 },
      { id: '<script>', viewedAt: Date.now() },
    ]),
  );
  expect(readHistory()).toEqual([]);
});
it('records once, clears locally, and accepts unavailable storage', () => {
  recordHistory(id);
  recordHistory(id);
  expect(readHistory()).toHaveLength(1);
  clearRecentlyViewed();
  expect(readHistory()).toEqual([]);
  vi.stubGlobal('window', {
    get localStorage() {
      throw new Error('disabled');
    },
    dispatchEvent: vi.fn(),
  });
  expect(() => recordHistory(id)).not.toThrow();
  expect(readHistory()).toEqual([]);
});
