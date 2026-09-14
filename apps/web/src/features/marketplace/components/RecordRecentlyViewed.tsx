'use client';

import { useRecordRecentlyViewed } from '../hooks/use-recently-viewed';
import type { PublicListing } from '../hooks/use-public-listings';

/**
 * Bridges the server-rendered listing detail page into the client-only
 * localStorage write - renders nothing, just records the view on mount.
 */
export function RecordRecentlyViewed({ listing }: { listing: PublicListing }) {
  useRecordRecentlyViewed(listing);
  return null;
}
