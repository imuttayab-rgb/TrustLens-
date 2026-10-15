/** Regression coverage and test support for post ad helpers.test. */
import { describe, expect, it, vi } from 'vitest';
import {
  checkVideo,
  formatSeconds,
  furthestReachableStep,
  geocodeAddress,
  matchCityArea,
  missingForPublish,
} from './post-ad-helpers';

const complete = {
  photoCount: 1,
  hasVideo: true,
  latitude: 31.47,
  longitude: 74.41,
  addressLine: 'Test House 1, Sample Street, Lahore',
};

describe('missingForPublish (mirrors backend listing_media_missing)', () => {
  it('accepts 1 photo + video + full location', () => {
    expect(missingForPublish(complete)).toEqual([]);
  });
  it('needs a photo, a video and the full location', () => {
    expect(missingForPublish({ ...complete, photoCount: 0 })).toEqual(['photo']);
    expect(missingForPublish({ ...complete, hasVideo: false })).toEqual(['video']);
    expect(missingForPublish({ ...complete, latitude: null })).toEqual(['location']);
    expect(missingForPublish({ ...complete, addressLine: '   ' })).toEqual(['location']);
  });
});

describe('checkVideo', () => {
  const ok = { type: 'video/mp4', sizeBytes: 5_000_000, durationSeconds: 25 };
  it('accepts MP4 and recorder WebM with codecs', () => {
    expect(checkVideo(ok)).toBeNull();
    expect(checkVideo({ ...ok, type: 'video/webm;codecs=vp9' })).toBeNull();
  });
  it('rejects .mov, oversize, too short and too long', () => {
    expect(checkVideo({ ...ok, type: 'video/quicktime' })).toMatch(/MP4 or WebM/);
    expect(checkVideo({ ...ok, sizeBytes: 51 * 1024 * 1024 })).toMatch(/50 MB/);
    expect(checkVideo({ ...ok, durationSeconds: 4 })).toMatch(/at least 10/);
    expect(checkVideo({ ...ok, durationSeconds: 75 })).toMatch(/at most 60/);
  });
  it('does not block when the browser cannot read the length', () => {
    expect(checkVideo({ ...ok, durationSeconds: null })).toBeNull();
  });
  it('formats the timer', () => {
    expect(formatSeconds(42)).toBe('0:42');
    expect(formatSeconds(60)).toBe('1:00');
  });
});

describe('matchCityArea', () => {
  it('maps an OpenStreetMap address onto the app city and area list', () => {
    expect(matchCityArea({ city: 'Lahore', suburb: 'DHA Phase 6', state: 'Punjab' })).toEqual({
      city: 'Lahore',
      area: 'DHA',
      province: 'Punjab',
    });
  });
  it('falls back to Other and an empty area when nothing matches', () => {
    const result = matchCityArea({ town: 'Unknown Town', state: 'Gilgit-Baltistan' });
    expect(result.city).toBe('Other');
    expect(result.area).toBe('');
    expect(result.province).toBe('Gilgit-Baltistan');
  });
});

describe('geocodeAddress', () => {
  it('queries Pakistan-only English results and maps the top hit', async () => {
    const fetchImpl = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify([
            {
              lat: '31.4697',
              lon: '74.4120',
              display_name: 'Street 5, DHA Phase 6, Lahore, Punjab, Pakistan',
              address: { city: 'Lahore', suburb: 'DHA Phase 6', state: 'Punjab' },
            },
          ]),
          { status: 200 },
        ),
      ),
    );
    const hit = await geocodeAddress('Street 5, DHA Phase 6, Lahore', {
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    const url = String((fetchImpl.mock.calls[0] as unknown[])[0]);
    expect(url).toContain('countrycodes=pk');
    expect(url).toContain('accept-language=en');
    expect(hit).toMatchObject({
      latitude: 31.4697,
      longitude: 74.412,
      city: 'Lahore',
      area: 'DHA',
    });
  });
  it('returns null for no result and skips very short input', async () => {
    const fetchImpl = vi.fn(() => Promise.resolve(new Response('[]', { status: 200 })));
    expect(
      await geocodeAddress('abc', { fetchImpl: fetchImpl as unknown as typeof fetch }),
    ).toBeNull();
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(
      await geocodeAddress('Nowhere street', { fetchImpl: fetchImpl as unknown as typeof fetch }),
    ).toBeNull();
  });
});

describe('furthestReachableStep', () => {
  it('opens later steps only after a draft, a photo and a video exist', () => {
    expect(furthestReachableStep({ hasDraft: false, photoCount: 0, hasVideo: false })).toBe(0);
    expect(furthestReachableStep({ hasDraft: true, photoCount: 1, hasVideo: false })).toBe(1);
    expect(furthestReachableStep({ hasDraft: true, photoCount: 1, hasVideo: true })).toBe(3);
  });
});
