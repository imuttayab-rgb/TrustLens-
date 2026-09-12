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
}: {
  latitude: number | null;
  longitude: number | null;
  onChange: (lat: number, lng: number) => void;
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
    // Initialised once on mount - a later lat/lng prop change (e.g. the
    // form resetting) is not fed back in, since the only source of truth
    // for the pin's position while this component is mounted is the map
    // itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-2">
      <span className="text-sm font-medium">Pin the exact location (optional)</span>
      <div
        id={containerId}
        ref={containerRef}
        className="h-56 w-full overflow-hidden rounded-lg border border-border bg-muted"
      />
      <p className="text-xs text-muted-foreground">
        Click or drag the pin. Map data from OpenStreetMap. This is separate from the city/area
        above and is only shown to buyers as a &ldquo;view on map&rdquo; link, never your exact
        address unless you place the pin there yourself.
      </p>
    </div>
  );
}
