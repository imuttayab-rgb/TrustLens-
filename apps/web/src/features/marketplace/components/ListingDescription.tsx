'use client';

import { useState } from 'react';

/** Collapses a long description to a few lines with a "See more" toggle -
 * most listings are short enough this never triggers. */
export function ListingDescription({ description }: { description: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = description.length > 320;

  return (
    <div>
      <p
        className={
          expanded || !long
            ? 'whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground'
            : 'line-clamp-4 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground'
        }
      >
        {description}
      </p>
      {long && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="mt-1 text-sm font-medium text-brand hover:underline"
        >
          {expanded ? 'See less' : 'See more'}
        </button>
      )}
    </div>
  );
}
