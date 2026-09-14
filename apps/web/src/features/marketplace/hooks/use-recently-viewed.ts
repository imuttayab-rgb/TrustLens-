'use client';

import { useEffect, useState } from 'react';
import type { PublicListing } from './use-public-listings';

const STORAGE_KEY = 'trustlens:recently-viewed';
const MAX_ITEMS = 12;

/**
 * Client-only, per-browser history of viewed listings (MKT-01). No backend
 * involvement - this is a convenience trail, not data anyone else needs to
 * see or that should survive a device switch, so localStorage is the right
 * tool rather than a new endpoint and table.
 */
function readRecentlyViewed(): PublicListing[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as PublicListing[]) : [];
  } catch {
    return [];
  }
}

export function recordRecentlyViewed(listing: PublicListing): void {
  try {
    const existing = readRecentlyViewed().filter((item) => item.id !== listing.id);
    const next = [listing, ...existing].slice(0, MAX_ITEMS);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Private browsing / storage quota / disabled storage - a lost history
    // entry is not worth surfacing an error over.
  }
}

/** Reads the trail, excluding whichever listing the caller is currently viewing. */
export function useRecentlyViewed(excludeId?: string): PublicListing[] {
  const [items, setItems] = useState<PublicListing[]>([]);

  useEffect(() => {
    setItems(readRecentlyViewed());
  }, []);

  return excludeId ? items.filter((item) => item.id !== excludeId) : items;
}

/** Records the given listing as viewed once, on mount. */
export function useRecordRecentlyViewed(listing: PublicListing | null): void {
  useEffect(() => {
    if (listing) recordRecentlyViewed(listing);
    // Only the id needs to retrigger this - the rest of the object is
    // stable for a given listing within one page view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listing?.id]);
}
