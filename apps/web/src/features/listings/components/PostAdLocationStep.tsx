/** Reusable UI rendering and interaction component: PostAdLocationStep. */
'use client';

import { CityPicker } from '@/features/location';
import {
  areasForCity,
  citiesInProvince,
  provinceOfCity,
  PAKISTAN_PROVINCES,
} from '@trustlens/constants';
import { Alert, Button, Spinner } from '@trustlens/ui';
import { EyeOff, LocateFixed, MapPin, Search, ShieldCheck } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useRef, useState } from 'react';
import { geocodeAddress, MAX_ADDRESS_CHARS } from './post-ad-helpers';

// Leaflet touches `window` at import time, so the map is client-only.
const LocationPicker = dynamic(() => import('./LocationPicker').then((m) => m.LocationPicker), {
  ssr: false,
  loading: () => (
    <div className="h-72 w-full animate-pulse rounded-lg border border-border bg-muted" />
  ),
});

export interface LocationValue {
  addressLine: string;
  city: string;
  area: string;
  latitude: number | null;
  longitude: number | null;
}

const selectClass =
  'h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring';

export function PostAdLocationStep({
  value,
  onChange,
  optionalAddress = false,
}: {
  optionalAddress?: boolean;
  value: LocationValue;
  onChange: (next: LocationValue) => void;
}) {
  const [selectedProvince, setSelectedProvince] = useState('');
  const province = selectedProvince || provinceOfCity(value.city) || '';
  const cities = citiesInProvince(province);
  const [searching, setSearching] = useState(false);
  const [message, setMessage] = useState<{
    tone: 'success' | 'warning' | 'error';
    text: string;
  } | null>(null);
  const lastLookup = useRef(0);
  const areas = areasForCity(value.city);

  async function findOnMap() {
    // Nominatim's free-use policy allows one request per second.
    if (Date.now() - lastLookup.current < 1100) return;
    lastLookup.current = Date.now();
    const query = [
      value.addressLine,
      value.area,
      value.city !== 'Other' ? value.city : '',
      'Pakistan',
    ]
      .filter(Boolean)
      .join(', ');
    setSearching(true);
    setMessage(null);
    try {
      let hit = await geocodeAddress(query);
      // House numbers are often missing from OpenStreetMap; retry with the
      // area and city only so the pin at least lands in the right place.
      if (!hit && (value.area || value.city)) {
        await new Promise((resolve) => setTimeout(resolve, 1100));
        hit = await geocodeAddress([value.area, value.city, 'Pakistan'].filter(Boolean).join(', '));
      }
      if (!hit) {
        setMessage({
          tone: 'warning',
          text: 'Address not found on the map. Check the spelling, or click the map to place the pin yourself.',
        });
        return;
      }
      const city = value.city || hit.city;
      onChange({
        ...value,
        city,
        area: value.area || (hit.city === city ? hit.area : ''),
        latitude: hit.latitude,
        longitude: hit.longitude,
      });
      setMessage({
        tone: 'success',
        text: `Pinned near: ${hit.displayName}. Drag the pin if it is not exactly on your place.`,
      });
    } catch (err) {
      setMessage({
        tone: 'error',
        text: err instanceof Error ? err.message : 'Map search failed. Try again in a few seconds.',
      });
    } finally {
      setSearching(false);
    }
  }

  const pinned = value.latitude !== null && value.longitude !== null;

  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <h2 className="text-base font-semibold">
          Full address{' '}
          {optionalAddress ? (
            <span className="font-normal text-muted-foreground">(optional)</span>
          ) : (
            <span className="text-destructive">*</span>
          )}
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          House, street, block or phase, area and city. This stays private: buyers never see it.
        </p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <MapPin
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <input
              id="post-ad-address"
              aria-label="Full address"
              value={value.addressLine}
              maxLength={MAX_ADDRESS_CHARS}
              onChange={(e) => onChange({ ...value, addressLine: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void findOnMap();
                }
              }}
              placeholder="e.g. House 12, Street 5, Sector C, DHA Phase 6, Lahore"
              className="h-11 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <Button
            type="button"
            onClick={() => void findOnMap()}
            disabled={searching || value.addressLine.trim().length < 5}
            className="h-11 bg-brand text-white hover:bg-brand/90"
          >
            {searching ? <Spinner /> : <Search className="mr-2 h-4 w-4" aria-hidden="true" />}
            Find on map
          </Button>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <label className="space-y-1 text-sm font-medium">
            <span>Province / region</span>
            <select
              aria-label="Province / region"
              value={province}
              onChange={(event) => {
                setSelectedProvince(event.target.value);
                onChange({ ...value, city: '', area: '', latitude: null, longitude: null });
              }}
              className={selectClass}
            >
              <option value="">All provinces / regions</option>
              {Object.keys(PAKISTAN_PROVINCES).map((region) => (
                <option key={region} value={region}>
                  {region}
                </option>
              ))}
            </select>
          </label>
          <div className="space-y-1 text-sm font-medium">
            <span>
              City <span className="text-destructive">*</span>
            </span>
            <CityPicker
              value={value.city}
              onChange={(city) =>
                onChange({ ...value, city, area: '', latitude: null, longitude: null })
              }
              cities={cities}
              province={province}
              allowOther
              className={selectClass}
            />
          </div>
          <label className="space-y-1 text-sm font-medium">
            <span>Area {!optionalAddress && <span className="text-destructive">*</span>}</span>
            <select
              aria-label="Area"
              value={value.area}
              onChange={(e) => onChange({ ...value, area: e.target.value })}
              className={selectClass}
              disabled={!value.city}
            >
              <option value="">Select area</option>
              {areas.map((area) => (
                <option key={area} value={area}>
                  {area}
                </option>
              ))}
            </select>
          </label>
        </div>

        {message && (
          <Alert
            tone={message.tone === 'success' ? 'success' : message.tone}
            title={message.tone === 'success' ? 'Location found' : 'Map search'}
            className="mt-4"
          >
            {message.text}
          </Alert>
        )}
      </section>

      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-1.5 text-base font-semibold">
            <LocateFixed className="h-4 w-4 text-brand" aria-hidden="true" />
            Pin on map{' '}
            {optionalAddress ? (
              <span className="font-normal text-muted-foreground">(optional)</span>
            ) : (
              <span className="text-destructive">*</span>
            )}
          </h2>
          <span
            className={
              pinned
                ? 'rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700'
                : 'rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-700'
            }
          >
            {pinned ? 'Pin placed' : 'No pin yet'}
          </span>
        </div>
        <div className="mt-3">
          <LocationPicker
            latitude={value.latitude}
            longitude={value.longitude}
            onChange={(lat, lng) => onChange({ ...value, latitude: lat, longitude: lng })}
            label={null}
            heightClass="h-72"
            hint="Press Find on map, then drag the pin onto your exact place, or click the map. Map data: OpenStreetMap."
          />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 p-3 text-xs">
            <EyeOff className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
            <p>
              <span className="font-semibold">Private to you:</span> full address and exact pin.
              Used only for your ad and safety checks.
            </p>
          </div>
          <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 p-3 text-xs">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
            <p>
              <span className="font-semibold">Buyers see:</span> area and city with an approximate
              circle (about 1 km), never your house or street.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
