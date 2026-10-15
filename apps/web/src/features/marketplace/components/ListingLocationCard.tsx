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
  // No marker: a pin would look like an exact address. The coordinate is
  // already rounded server-side; the circle overlay shows it as an AREA.
  const embedSrc = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik`;

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold">
        <MapPin className="h-4 w-4 text-brand" aria-hidden="true" />
        Approximate location
      </h2>
      <p className="mt-1 text-sm font-medium">{area ? `${area}, ${city}` : (city ?? 'Pakistan')}</p>
      <p className="text-xs text-muted-foreground">Exact address hidden for privacy</p>

      <div className="relative mt-3 overflow-hidden rounded-lg border border-border">
        <iframe
          title="Approximate listing location"
          src={embedSrc}
          className="h-48 w-full"
          loading="lazy"
        />
        {/* Decorative ~1 km area ring centred on the rounded coordinate. */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-1/2 top-1/2 h-28 w-28 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-brand bg-brand/15"
        />
        <span className="pointer-events-none absolute bottom-2 left-2 rounded-full bg-white/90 px-2 py-0.5 text-[11px] font-medium text-foreground shadow">
          Approx. area · about 1 km
        </span>
      </div>

      <NearbyVenues city={city} />
    </div>
  );
}
