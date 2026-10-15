import { describe, expect, it } from 'vitest';
import { safeNext } from './safe-next';
describe('login return path', () => {
  it.each([
    'https://evil.invalid',
    '//evil.invalid',
    '/\\evil.invalid',
    '/%2fevil.invalid',
    '/%255cevil.invalid',
    '/\nevil.invalid',
    '/%zz',
  ])('rejects unsafe path %s', (path) => {
    expect(safeNext(path)).toBe('/dashboard');
  });
  it('preserves the requested seller page and query', () => {
    expect(safeNext('/dashboard/listings/new?draft=abc')).toBe('/dashboard/listings/new?draft=abc');
  });
});
