'use client';

import 'leaflet/dist/leaflet.css';
import type { Map as LeafletMap, Marker as LeafletMarker } from 'leaflet';
import { useEffect, useId, useRef } from 'react';

//: Lahore. A neutral default centre for a Pakistani marketplace when no
//: coordinate has been picked yet.
const DEFAULT_CENTER: [number, number] = [31.5204, 74.3587];

/**
 * Drop-a-pin location picker for the listing form.
 *
 * Leaflet + OpenStreetMap tiles, not Google Maps: no API key, no billing
 * account, no signup - OSM's tile server is free for this traffic volume
 * and the alternative (a Google Maps key) requires linking a card even for
 * the free tier, which is a real barrier for an FYP with no budget.
 *
 * `leaflet` is imported dynamically inside the effect rather than at module
 * scope - its core touches `window` at import time, which breaks under
 * Next's server-side render of this file even with 'use client'.
 */
export function LocationPicker({
  latitude,
  longitude,
  onChange,
  label = 'Pin the exact location (optional)',
  hint,
  heightClass = 'h-56',
}: {
  latitude: number | null;
  longitude: number | null;
  onChange: (lat: number, lng: number) => void;
  /** Heading above the map; the Post-an-Ad wizard uses its own wording. */
  label?: string | null;
  /** Replaces the default helper text under the map. */
  hint?: string;
  heightClass?: string;
}) {
  const containerId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markerRef = useRef<LeafletMarker | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;

    void import('leaflet').then((leafletModule) => {
      if (cancelled || !containerRef.current || mapRef.current) return;
      const L = leafletModule.default;

      // Leaflet's default marker icon points at relative image paths that
      // Next's bundler cannot resolve - point them at the CDN instead.
      delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      });

      const center: [number, number] =
        latitude !== null && longitude !== null ? [latitude, longitude] : DEFAULT_CENTER;

      const map = L.map(containerRef.current).setView(center, latitude !== null ? 14 : 11);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);

      const marker = L.marker(center, { draggable: true }).addTo(map);
      marker.on('dragend', () => {
        const pos = marker.getLatLng();
        onChangeRef.current(pos.lat, pos.lng);
      });
      map.on('click', (e) => {
        marker.setLatLng(e.latlng);
        onChangeRef.current(e.latlng.lat, e.latlng.lng);
      });

      mapRef.current = map;
      markerRef.current = marker;
    });

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
    // Initialised once on mount; later prop changes are handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Post-an-Ad v2: typing an address and pressing "Find on map" changes the
  // coordinate from OUTSIDE the map. Move the pin there and zoom in. A
  // change that came from dragging the pin already matches, so nothing jumps.
  useEffect(() => {
    const map = mapRef.current;
    const marker = markerRef.current;
    if (!map || !marker || latitude === null || longitude === null) return;
    const current = marker.getLatLng();
    if (Math.abs(current.lat - latitude) < 1e-7 && Math.abs(current.lng - longitude) < 1e-7) {
      return;
    }
    marker.setLatLng([latitude, longitude]);
    map.setView([latitude, longitude], Math.max(map.getZoom(), 16));
  }, [latitude, longitude]);

  return (
    <div className="space-y-2">
      {label && <span className="text-sm font-medium">{label}</span>}
      <div
        id={containerId}
        ref={containerRef}
        className={`${heightClass} relative z-0 w-full overflow-hidden rounded-lg border border-border bg-muted`}
      />
      <p className="text-xs text-muted-foreground">
        {hint ??
          'Click or drag the pin. Map data from OpenStreetMap. Buyers only ever see an approximate area (about 1 km), never your exact address.'}
      </p>
    </div>
  );
}
