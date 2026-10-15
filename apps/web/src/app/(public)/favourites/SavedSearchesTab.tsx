/** Next.js route/layout composition for (public)/favourites: SavedSearchesTab. */
'use client';

import {
  savedSearchToUrl,
  useDeleteSavedSearch,
  useSavedSearches,
  type SavedSearch,
} from '@/features/marketplace';
import { LISTING_CATEGORY_LABELS } from '@trustlens/constants';
import { Alert, Button, Spinner } from '@trustlens/ui';
import { ArrowRight, Search, Trash2 } from 'lucide-react';
import Link from 'next/link';

/** A one-line, human summary of what a saved search filters for - these are
 * re-runnable bookmarks (FAV-01), not a stored result set, so this is the
 * only place their criteria need to read nicely. */
function describeSavedSearch(search: SavedSearch): string {
  const parts: string[] = [];
  if (search.q) parts.push(`"${search.q}"`);
  if (search.category) parts.push(LISTING_CATEGORY_LABELS[search.category]);
  if (search.area) parts.push(`${search.area}, ${search.city}`);
  else if (search.city) parts.push(search.city);
  if (search.minPrice !== null || search.maxPrice !== null) {
    const min = search.minPrice !== null ? search.minPrice.toLocaleString() : '0';
    const max = search.maxPrice !== null ? search.maxPrice.toLocaleString() : '∞';
    parts.push(`PKR ${min} – ${max}`);
  }
  return parts.length > 0 ? parts.join(' · ') : 'All listings';
}

export function SavedSearchesTab() {
  const { data: searches, isPending, isError } = useSavedSearches();
  const deleteSearch = useDeleteSavedSearch();

  if (isPending) {
    return (
      <div className="flex justify-center py-16">
        <Spinner label="Loading saved searches" />
      </div>
    );
  }

  if (isError) {
    return (
      <Alert tone="error" title="Could not load saved searches">
        Try again in a moment.
      </Alert>
    );
  }

  if (searches.length === 0) {
    return (
      <Alert tone="info" title="No saved searches yet">
        Apply filters on Browse, then use &quot;Save this search&quot; to bookmark them here.
      </Alert>
    );
  }

  return (
    <div className="space-y-3">
      {searches.map((search) => (
        <div
          key={search.id}
          className="flex items-center gap-3 rounded-lg border border-border bg-card p-3"
        >
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand/10 text-brand">
            <Search className="h-4 w-4" aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{search.name}</p>
            <p className="truncate text-xs text-muted-foreground">{describeSavedSearch(search)}</p>
          </div>
          <Link
            href={savedSearchToUrl(search)}
            className="flex shrink-0 items-center gap-1 text-sm font-medium text-brand hover:underline"
          >
            Run search
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
          <Button
            variant="outline"
            size="icon"
            aria-label={`Delete saved search ${search.name}`}
            disabled={deleteSearch.isPending}
            onClick={() => deleteSearch.mutate(search.id)}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      ))}
    </div>
  );
}
