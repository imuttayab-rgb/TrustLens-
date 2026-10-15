/** Regression coverage and test support for browse discovery.test. */
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
const state = vi.hoisted(() => ({ params: '', locale: 'en', query: vi.fn() }));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(state.params),
}));
vi.mock('next-intl', () => ({ useLocale: () => state.locale }));
vi.mock('@/lib/auth/use-session', () => ({ useSession: () => ({ data: null }) }));
vi.mock('@/features/assistant', () => ({ askAssistant: vi.fn() }));
vi.mock('@/features/location', () => ({ CityPicker: () => null }));
vi.mock('@/features/marketplace', () => ({
  usePublicListings: state.query,
  useFavoriteIds: () => ({ data: new Set() }),
  useAddFavorite: () => ({ mutate: vi.fn(), isPending: false }),
  useRemoveFavorite: () => ({ mutate: vi.fn(), isPending: false }),
  RecentlyViewedStrip: () => null,
  SavedSearchBar: () => null,
  RelatedRecommendations: () => null,
}));
vi.mock('./BrowseResultCard', () => ({
  BrowseResultCard: ({ listing }: { listing: { id: string } }) => (
    <article data-test-ad={listing.id} />
  ),
}));
vi.mock('@/features/categories', () => import('../../../features/categories/CategoryFilters'));
import BrowsePage from './page';

describe('browse discovery regressions', () => {
  afterEach(() => vi.unstubAllGlobals());
  beforeEach(() => {
    vi.stubGlobal('React', React);
    state.params = '';
    state.locale = 'en';
    state.query.mockReset();
    state.query.mockReturnValue({
      data: { total: 150, items: Array.from({ length: 24 }, (_, i) => ({ id: `synthetic-${i}` })) },
      isPending: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    });
  });
  it('requests a full 24-ad page and preserves category, location and search', () => {
    state.params = 'categoryNodeId=mobiles%2Fmobile-phones&city=Lahore&q=S21%2B&page=2';
    const html = renderToStaticMarkup(<BrowsePage />);
    expect(state.query).toHaveBeenCalledWith(
      expect.objectContaining({
        limit: 24,
        offset: 24,
        categoryNodeId: 'mobiles/mobile-phones',
        city: 'Lahore',
        q: 'S21+',
      }),
    );
    expect(html.match(/data-test-ad=/g)).toHaveLength(24);
    expect(html).toContain('aria-label="Pagination"');
    expect(html).toMatch(/<\/section><nav aria-label="Pagination"/);
  });
  it('does not show irrelevant Material/Size or a duplicate broad category control for Mobiles', () => {
    state.params = 'categoryNodeId=mobiles';
    const html = renderToStaticMarkup(<BrowsePage />);
    expect(html).not.toContain('aria-label="Material"');
    expect(html).not.toContain('aria-label="Size"');
    expect(html).toContain('Choose a subcategory for relevant specification filters.');
    expect(html).not.toContain('Legacy category');
  });
  it('still offers phone-specific fields at the phone leaf', () => {
    state.params = 'categoryNodeId=mobiles%2Fmobile-phones';
    const html = renderToStaticMarkup(<BrowsePage />);
    expect(html).toContain('aria-label="Brand"');
    expect(html).toContain('aria-label="RAM minimum"');
    expect(html).toContain('aria-label="Storage minimum"');
  });
  it('shows retry on request failure instead of claiming no listings exist', () => {
    state.query.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      isFetching: false,
      refetch: vi.fn(),
    });
    const html = renderToStaticMarkup(<BrowsePage />);
    expect(html).toContain('Try again');
    expect(html).not.toContain('No listings found');
    expect(html).not.toContain('aria-label="Pagination"');
  });
});
