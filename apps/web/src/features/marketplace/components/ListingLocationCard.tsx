import { NearbyVenues } from './NearbyVenues';
import { MapPin } from 'lucide-react';

/**
 * Approximate location - the API already rounds the coordinate to ~1.1km
 * (LOC-01) before it ever reaches here, so the embed's bounding box just
 * frames that same imprecision rather than adding its own.
 */
export function ListingLocationCard({
  latitude,
  longitude,
  city,
  area,
}: {
  latitude: number;
  longitude: number;
  city: string | null;
  area: string | null;
}) {
  const delta = 0.015;
  const bbox = [longitude - delta, latitude - delta, longitude + delta, latitude + delta].join(',');
  const embedSrc = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${latitude},${longitude}`;

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold">
        <MapPin className="h-4 w-4 text-brand" aria-hidden="true" />
        Approximate location
      </h2>
      <p className="mt-1 text-sm font-medium">{area ? `${area}, ${city}` : (city ?? 'Pakistan')}</p>
      <p className="text-xs text-muted-foreground">Exact address hidden for privacy</p>

      <div className="mt-3 overflow-hidden rounded-lg border border-border">
        <iframe
          title="Approximate listing location"
          src={embedSrc}
          className="h-48 w-full"
          loading="lazy"
        />
      </div>

      <NearbyVenues city={city} />
    </div>
  );
}
