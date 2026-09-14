'use client';

import { useSession } from '@/lib/auth/use-session';
import { toApiError } from '@trustlens/api-client';
import { Button } from '@trustlens/ui';
import { Bookmark, X } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import {
  savedSearchToUrl,
  useCreateSavedSearch,
  useDeleteSavedSearch,
  useSavedSearches,
} from '../hooks/use-saved-searches';

/**
 * FAV-01's saved searches: a "Save this search" button (only meaningful
 * once some filter is active) plus a strip of the user's existing saved
 * searches, each just a link back to `/browse` with the filter re-applied -
 * no separate results view to keep in sync with the real one.
 */
export function SavedSearchBar({
  hasFilters,
  currentFilters,
}: {
  hasFilters: boolean;
  currentFilters: {
    category: string | null;
    q: string | null;
    city: string | null;
    area: string | null;
    minPrice: number | null;
    maxPrice: number | null;
  };
}) {
  const { data: session } = useSession();
  const { data: searches } = useSavedSearches();
  const createSearch = useCreateSavedSearch();
  const deleteSearch = useDeleteSavedSearch();
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (!session) return null;

  async function handleSave() {
    setError(null);
    try {
      await createSearch.mutateAsync({ name: name.trim(), ...currentFilters });
      setNaming(false);
      setName('');
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      {hasFilters &&
        (naming ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void handleSave();
            }}
            className="flex items-center gap-1.5"
          >
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Name this search"
              className="h-8 w-40 rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Button type="submit" size="sm" disabled={!name.trim() || createSearch.isPending}>
              Save
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setNaming(false)}>
              Cancel
            </Button>
          </form>
        ) : (
          <Button variant="outline" size="sm" onClick={() => setNaming(true)}>
            <Bookmark className="h-4 w-4" aria-hidden="true" />
            Save this search
          </Button>
        ))}
      {error && <p className="text-xs text-destructive">{error}</p>}

      {searches && searches.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {searches.map((search) => (
            <span
              key={search.id}
              className="flex items-center gap-1 rounded-full border border-border py-1 pl-3 pr-1 text-xs"
            >
              <Link href={savedSearchToUrl(search)} className="hover:underline">
                {search.name}
              </Link>
              <button
                type="button"
                aria-label={`Delete saved search ${search.name}`}
                disabled={deleteSearch.isPending}
                onClick={() => deleteSearch.mutate(search.id)}
                className="grid h-4 w-4 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="h-3 w-3" aria-hidden="true" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
