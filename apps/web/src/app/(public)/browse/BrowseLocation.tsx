/** Next.js route/layout composition for (public)/browse: BrowseLocation. */
'use client';

import { CityPicker } from '@/features/location';
import {
  areasForCity,
  citiesInProvince,
  PAKISTAN_PROVINCES,
  provinceOfCity,
} from '@trustlens/constants';
import { ChevronDown, Loader2, MapPin, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import styles from './browse-reference.module.css';

export function BrowseLocation({
  city,
  area,
  nearby,
  locating,
  locationError,
  onApply,
  onNearby,
  onClearNearby,
}: {
  city: string | null;
  area: string | null;
  nearby: number | null;
  locating: boolean;
  locationError: string | null;
  onApply: (city: string | null, area: string | null) => void;
  onNearby: () => void;
  onClearNearby: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [province, setProvince] = useState<string | null>(provinceOfCity(city));
  const [selectedCity, setSelectedCity] = useState(city);
  const [selectedArea, setSelectedArea] = useState(area);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const popover = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    function closeOutside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function escape(event: KeyboardEvent) {
      // The nested city dialog owns its own Escape action.
      if (
        event.key === 'Escape' &&
        (event.target as HTMLElement).closest('[role="dialog"]') === popover.current
      ) {
        event.preventDefault();
        setOpen(false);
        trigger.current?.focus();
      }
    }
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', closeOutside);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);
  function close() {
    setOpen(false);
    trigger.current?.focus();
  }
  return (
    <div
      ref={root}
      className={styles.locationRoot}
      onBlur={(event) => {
        if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget))
          setOpen(false);
      }}
    >
      <button
        ref={trigger}
        type="button"
        className={styles.locationTrigger}
        aria-haspopup="dialog"
        aria-expanded={open}
        onKeyDown={(event) => {
          if (event.key === 'Escape') close();
        }}
        onClick={() => {
          if (!open) {
            setProvince(provinceOfCity(city));
            setSelectedCity(city);
            setSelectedArea(area);
          }
          setOpen(!open);
        }}
      >
        <MapPin aria-hidden="true" />
        <span>
          {[area, city].filter(Boolean).join(', ') ||
            (nearby !== null ? `Nearby (${nearby} km)` : 'All Pakistan')}
        </span>
        <ChevronDown aria-hidden="true" />
      </button>
      {open && (
        <div
          ref={popover}
          role="dialog"
          aria-label="Choose search location"
          className={styles.locationPopover}
        >
          <div className={styles.popoverHeading}>
            <strong>Choose location</strong>
            <button type="button" aria-label="Close location" onClick={close}>
              <X aria-hidden="true" />
            </button>
          </div>
          <label>
            Province / region
            <select
              value={province ?? ''}
              onChange={(e) => {
                setProvince(e.target.value || null);
                setSelectedCity(null);
                setSelectedArea(null);
              }}
              className={styles.input ?? ''}
            >
              <option value="">All provinces / regions</option>
              {Object.keys(PAKISTAN_PROVINCES)
                .sort()
                .map((p) => (
                  <option key={p}>{p}</option>
                ))}
            </select>
          </label>
          <div>
            <span className={styles.fieldLabel}>City</span>
            <CityPicker
              value={selectedCity ?? ''}
              onChange={(value) => {
                setSelectedCity(value || null);
                setProvince(province || provinceOfCity(value));
                setSelectedArea(null);
              }}
              province={province}
              cities={citiesInProvince(province)}
              placeholder={province ? 'Search for your city' : 'All cities'}
              className={styles.input ?? ''}
            />
          </div>
          <label>
            Area
            <select
              className={styles.input ?? ''}
              value={selectedArea ?? ''}
              disabled={!selectedCity}
              onChange={(e) => setSelectedArea(e.target.value || null)}
            >
              <option value="">All areas</option>
              {(selectedCity ? areasForCity(selectedCity) : []).map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className={styles.primary}
            disabled={Boolean(province && !selectedCity)}
            onClick={() => {
              onApply(selectedCity, selectedArea);
              close();
            }}
          >
            Apply location
          </button>
          {province && !selectedCity && <p className={styles.hint}>Choose a city in {province}.</p>}
          <button
            type="button"
            className={styles.nearbyButton}
            onClick={nearby !== null ? onClearNearby : onNearby}
            disabled={locating}
          >
            {locating ? (
              <Loader2 className="animate-spin" aria-hidden="true" />
            ) : (
              <MapPin aria-hidden="true" />
            )}
            {locating
              ? 'Locating…'
              : nearby !== null
                ? 'Remove nearby filter'
                : 'Use my current location'}
          </button>
          {locationError && (
            <p role="status" className="text-xs text-destructive">
              {locationError}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
