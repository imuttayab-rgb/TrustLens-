import type { ListingCategory } from '@trustlens/constants';

/**
 * No `'use client'` here, deliberately: a Server Component (CategoryRow)
 * and a Client Component (SiteNav) both need this list, and importing a
 * plain value across that boundary from a client module hands the server
 * side a proxy instead of the real array - the exact trap `theme.ts`
 * documents. A plain shared module sidesteps it for both.
 *
 * Seven of the real catalog categories (never an invented one, like a
 * "Bikes" the schema has no slug for), plus a "More" link to the full list.
 */
export const NAV_CATEGORIES: ListingCategory[] = [
  'mobiles',
  'vehicles',
  'property-sale',
  'electronics',
  'home-appliances',
  'services',
  'fashion',
];
