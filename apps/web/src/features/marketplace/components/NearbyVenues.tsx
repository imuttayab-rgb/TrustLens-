'use client';

import { useSession } from '@/lib/auth/use-session';
import { useNearbyVenues } from '@/features/safemeet';
import { MapPin } from 'lucide-react';
import Link from 'next/link';

/** A taste of the real, staff-curated SafeMeet spots near this listing's
 * city (SAFE-01) - venue browsing needs a session, so this only renders for
 * a signed-in visitor; an anonymous one still sees the Propose SafeMeet
 * button, which sends them to log in first. */
export function NearbyVenues({ city }: { city: string | null }) {
  const { data: session } = useSession();
  const { data: venues } = useNearbyVenues(session ? city : null);

  if (!session || !venues || venues.length === 0) return null;

  return (
    <div className="mt-3 space-y-1.5 border-t border-border pt-3">
      <p className="text-xs font-medium text-muted-foreground">
        Suggested public meeting spots nearby
      </p>
      <ul className="space-y-1.5">
        {venues.slice(0, 3).map((venue) => (
          <li key={venue.id} className="flex items-start gap-2 text-sm">
            <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand" aria-hidden="true" />
            <span className="min-w-0">
              <span className="font-medium">{venue.name}</span>
              <span className="block truncate text-xs text-muted-foreground">{venue.address}</span>
            </span>
          </li>
        ))}
      </ul>
      <Link
        href="/safety"
        className="inline-block text-xs font-medium text-brand underline-offset-4 hover:underline"
      >
        Safety tips
      </Link>
    </div>
  );
}
