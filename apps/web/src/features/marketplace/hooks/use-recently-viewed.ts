/** Coordinate browser history IDs with current public listing data. */
'use client';
import { useEffect, useState } from 'react';
import { useQueries } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { toApiError } from '@trustlens/api-client';
import type { PublicListing } from './use-public-listings';
import {
  HISTORY_EVENT,
  HISTORY_KEY,
  readHistory,
  recordHistory,
  type HistoryEntry,
} from '../lib/recent-history';
export { clearRecentlyViewed } from '../lib/recent-history';
type HistoryCard = Pick<PublicListing, 'id' | 'title' | 'thumbnailUrl' | 'imageUrl'>;
export function recordRecentlyViewed(listing: PublicListing): void {
  recordHistory(listing.id);
}

export function useRecentlyViewed(excludeId?: string): HistoryCard[] {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  useEffect(() => {
    const refresh = () => setEntries(readHistory());
    const onStorage = (event: StorageEvent) => {
      if (event.key === HISTORY_KEY || event.key === null) refresh();
    };
    refresh();
    window.addEventListener(HISTORY_EVENT, refresh);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener(HISTORY_EVENT, refresh);
      window.removeEventListener('storage', onStorage);
    };
  }, []);
  const results = useQueries({
    queries: entries
      .filter((entry) => entry.id !== excludeId)
      .map(({ id }) => ({
        queryKey: ['recent-listing-card', id],
        staleTime: 60_000,
        retry: false,
        queryFn: async (): Promise<HistoryCard> => {
          const result = await api.GET('/api/v1/public/listings/{listing_id}', {
            params: { path: { listing_id: id } },
          });
          if (result.error) throw toApiError(result.error);
          const value = (
            result.data as unknown as {
              data: {
                id: string;
                title: string;
                images: { imageUrl: string; thumbnailUrl: string | null; isPrimary?: boolean }[];
              };
            }
          ).data;
          const image = value.images.find((item) => item.isPrimary) ?? value.images[0];
          return {
            id: value.id,
            title: value.title,
            imageUrl: image?.imageUrl ?? null,
            thumbnailUrl: image?.thumbnailUrl ?? null,
          };
        },
      })),
  });
  return results.flatMap((result) => (result.data ? [result.data] : []));
}
export function useRecordRecentlyViewed(listing: PublicListing | null): void {
  const id = listing?.id;
  useEffect(() => {
    if (id) recordHistory(id);
  }, [id]);
}
