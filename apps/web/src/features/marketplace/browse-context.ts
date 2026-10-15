'use client';

import { useSearchParams } from 'next/navigation';
import { browseLocation, withBrowseLocation } from '@trustlens/constants';

/** Location is URL-backed. Only allowlisted public location filters cross pages. */
export function useBrowseContext() {
  const params = useSearchParams();
  const location = browseLocation(params);
  return {
    ...location,
    href: (path: string) => withBrowseLocation(path, params),
    query: {
      city: location.city,
      area: location.area,
      nearLatitude: location.lat,
      nearLongitude: location.lng,
      radiusKm: location.radius,
    },
  };
}
