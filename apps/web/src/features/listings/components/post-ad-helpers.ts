/**
 * Pure helpers for the Post-an-Ad wizard (no React, no DOM), so the rules
 * the seller sees are unit-tested.
 *
 * IMPORTANT: these are UX checks only. The backend publication policy
 * (`listing_media_missing` in trustlens-core) is the real gate: an ad
 * without a photo, a video or a full map location never reaches buyers,
 * even if someone calls the API directly.
 */
import { areasForCity, PAKISTAN_CITIES, PAKISTAN_PROVINCES } from '@trustlens/constants';

export const MAX_PHOTOS = 10;
export const MIN_PHOTOS = 1;
export const MAX_VIDEO_BYTES = 50 * 1024 * 1024; // matches storage_max_video_upload_bytes
export const MIN_VIDEO_SECONDS = 10;
export const MAX_VIDEO_SECONDS = 60;
export const VIDEO_TYPES = ['video/mp4', 'video/webm'] as const;
export const MAX_ADDRESS_CHARS = 300; // matches the listings.address_line column

export const POST_AD_STEPS = [
  { id: 'details', label: 'Details' },
  { id: 'media', label: 'Photos & Video' },
  { id: 'location', label: 'Location' },
  { id: 'preview', label: 'Preview & Publish' },
] as const;
export type PostAdStepId = (typeof POST_AD_STEPS)[number]['id'];

/** What the media and location rule still needs (same order as backend). */
export function missingForPublish(input: {
  photoCount: number;
  policy?: 'physical' | 'virtual';
  hasVideo: boolean;
  latitude: number | null | undefined;
  longitude: number | null | undefined;
  addressLine: string | null | undefined;
}): ('photo' | 'video' | 'location')[] {
  const missing: ('photo' | 'video' | 'location')[] = [];
  if (input.policy === 'virtual') return [];
  if (input.photoCount < MIN_PHOTOS) missing.push('photo');
  if (!input.hasVideo) missing.push('video');
  if (
    input.latitude === null ||
    input.latitude === undefined ||
    input.longitude === null ||
    input.longitude === undefined ||
    !input.addressLine?.trim()
  ) {
    missing.push('location');
  }
  return missing;
}

export const MISSING_LABEL: Record<'photo' | 'video' | 'location', string> = {
  photo: 'Add at least 1 photo',
  video: 'Add a 10-60 second product video',
  location: 'Enter your full address and pin it on the map',
};

/**
 * Check a chosen or recorded clip before uploading it.
 * `durationSeconds` is null when the browser could not read it (some
 * MediaRecorder WebM files report Infinity until fully parsed); the recorder
 * then passes its own timer value instead.
 */
export function checkVideo(input: {
  type: string;
  sizeBytes: number;
  durationSeconds: number | null;
}): string | null {
  const baseType = input.type.split(';')[0]?.trim().toLowerCase() ?? '';
  if (!(VIDEO_TYPES as readonly string[]).includes(baseType)) {
    return 'Use an MP4 or WebM video. iPhone .mov files: record with "Record live video" instead.';
  }
  if (input.sizeBytes > MAX_VIDEO_BYTES) return 'The video must be 50 MB or smaller.';
  if (input.sizeBytes === 0) return 'The video file is empty.';
  if (input.durationSeconds !== null && Number.isFinite(input.durationSeconds)) {
    if (input.durationSeconds < MIN_VIDEO_SECONDS - 0.5) {
      return `The video must be at least ${MIN_VIDEO_SECONDS} seconds long.`;
    }
    if (input.durationSeconds > MAX_VIDEO_SECONDS + 0.5) {
      return `The video must be at most ${MAX_VIDEO_SECONDS} seconds long.`;
    }
  }
  return null;
}

/** "0:42" style label for the recorder timer and the video card. */
export function formatSeconds(total: number): string {
  const safe = Math.max(0, Math.round(total));
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, '0')}`;
}

/** Normalise a place name for loose comparison ("Phase 6" vs "phase-6"). */
function norm(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

/** Address parts returned by OpenStreetMap Nominatim (addressdetails=1). */
export interface GeocodeAddress {
  city?: string;
  town?: string;
  village?: string;
  county?: string;
  state_district?: string;
  state?: string;
  suburb?: string;
  neighbourhood?: string;
  quarter?: string;
  residential?: string;
  city_district?: string;
  road?: string;
}

export interface GeocodeHit {
  latitude: number;
  longitude: number;
  displayName: string;
  /** One of the app's city names, or 'Other' when not in the list. */
  city: string;
  /** One of that city's area names, or '' when nothing matched. */
  area: string;
  province: string | null;
}

/** Map a geocoder address onto the app's fixed city and area vocabulary. */
export function matchCityArea(address: GeocodeAddress): {
  city: string;
  area: string;
  province: string | null;
} {
  const cityCandidates = [
    address.city,
    address.town,
    address.village,
    address.county,
    address.state_district,
  ].filter((v): v is string => Boolean(v));
  let city = 'Other';
  for (const candidate of cityCandidates) {
    const found = PAKISTAN_CITIES.find(
      (known) => known !== 'Other' && norm(candidate).includes(norm(known)),
    );
    if (found) {
      city = found;
      break;
    }
  }
  const areaCandidates = [
    address.suburb,
    address.neighbourhood,
    address.quarter,
    address.residential,
    address.city_district,
    address.road,
  ].filter((v): v is string => Boolean(v));
  let area = '';
  const known = areasForCity(city).filter((a) => a !== 'Other');
  outer: for (const candidate of areaCandidates) {
    const c = norm(candidate);
    for (const option of known) {
      const o = norm(option);
      // "DHA Phase 6" -> "DHA"; "Gulberg III" -> "Gulberg".
      if (c === o || c.startsWith(`${o} `) || c.includes(` ${o} `) || c.endsWith(` ${o}`)) {
        area = option;
        break outer;
      }
    }
  }
  let province: string | null = null;
  for (const [name, cities] of Object.entries(PAKISTAN_PROVINCES)) {
    if ((cities as readonly string[]).includes(city)) province = name;
  }
  if (!province && address.state) province = address.state;
  return { city, area, province };
}

/**
 * Look up a typed address with the free OpenStreetMap Nominatim service.
 *
 * Usage policy: at most one request per second and no bulk use - so this
 * runs ONLY when the seller presses "Find on map", never per keystroke.
 * House numbers are often missing from OSM, so the pin usually lands on the
 * street or area and the seller drags it to the exact spot.
 */
export async function geocodeAddress(
  query: string,
  { signal, fetchImpl = fetch }: { signal?: AbortSignal; fetchImpl?: typeof fetch } = {},
): Promise<GeocodeHit | null> {
  const q = query.trim();
  if (q.length < 5) return null;
  const url =
    'https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=1' +
    `&countrycodes=pk&accept-language=en&q=${encodeURIComponent(q)}`;
  const response = await fetchImpl(url, {
    signal: signal ?? null,
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) throw new Error('The map search is busy. Try again in a few seconds.');
  const results = (await response.json()) as {
    lat: string;
    lon: string;
    display_name: string;
    address?: GeocodeAddress;
  }[];
  const top = results[0];
  if (!top) return null;
  const latitude = Number(top.lat);
  const longitude = Number(top.lon);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  return {
    latitude,
    longitude,
    displayName: top.display_name,
    ...matchCityArea(top.address ?? {}),
  };
}

/** Which steps the seller may open, given what already exists. */
export function furthestReachableStep(input: {
  hasDraft: boolean;
  photoCount: number;
  policy?: 'physical' | 'virtual';
  hasVideo: boolean;
}): number {
  if (!input.hasDraft) return 0;
  if (input.policy !== 'virtual' && (input.photoCount < MIN_PHOTOS || !input.hasVideo)) return 1;
  return 3;
}
