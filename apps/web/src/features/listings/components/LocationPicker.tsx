'use client';

import { useEffect, useId, useRef, useState } from 'react';

interface LatLng {
  lat: number;
  lng: number;
}

interface GoogleMapsMarker {
  setPosition(position: LatLng): void;
  addListener(event: string, handler: () => void): void;
  getPosition(): { lat(): number; lng(): number } | null;
}

interface GoogleMapsMap {
  addListener(
    event: string,
    handler: (e: { latLng: { lat(): number; lng(): number } | null }) => void,
  ): void;
  setCenter(position: LatLng): void;
}

interface GoogleMapsNamespace {
  Map: new (el: HTMLElement, options: Record<string, unknown>) => GoogleMapsMap;
  Marker: new (options: Record<string, unknown>) => GoogleMapsMarker;
}

declare global {
  interface Window {
    google?: { maps: GoogleMapsNamespace };
  }
}

//: Shared across every instance of this component on the page, so opening
//: two listing forms does not inject the script twice or race two callbacks.
let mapsLoader: Promise<GoogleMapsNamespace> | null = null;

function loadGoogleMaps(apiKey: string): Promise<GoogleMapsNamespace> {
  if (window.google?.maps) return Promise.resolve(window.google.maps);
  if (mapsLoader) return mapsLoader;

  mapsLoader = new Promise((resolve, reject) => {
    const callbackName = `__trustlensMapsReady_${Math.random().toString(36).slice(2)}`;
    (window as unknown as Record<string, () => void>)[callbackName] = () => {
      if (window.google?.maps) resolve(window.google.maps);
      else reject(new Error('Google Maps failed to initialise.'));
    };
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&callback=${callbackName}`;
    script.async = true;
    script.onerror = () => reject(new Error('Could not load Google Maps.'));
    document.head.appendChild(script);
  });
  return mapsLoader;
}

//: Lahore. A neutral default centre for a Pakistani marketplace when no
//: coordinate has been picked yet.
const DEFAULT_CENTER: LatLng = { lat: 31.5204, lng: 74.3587 };

/**
 * Drop-a-pin location picker for the listing form.
 *
 * Renders nothing at all when NEXT_PUBLIC_GOOGLE_MAPS_API_KEY is unset,
 * rather than an "unavailable" message - the city/area picker already
 * captures a usable location, so the map is a refinement, not something
 * whose absence needs explaining to a seller mid-form.
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
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  const containerId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<GoogleMapsMap | null>(null);
  const markerRef = useRef<GoogleMapsMarker | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    if (!apiKey || !containerRef.current) return;
    let cancelled = false;

    loadGoogleMaps(apiKey)
      .then((maps) => {
        if (cancelled || !containerRef.current) return;
        const center =
          latitude !== null && longitude !== null
            ? { lat: latitude, lng: longitude }
            : DEFAULT_CENTER;
        const map = new maps.Map(containerRef.current, {
          center,
          zoom: latitude !== null ? 14 : 11,
          streetViewControl: false,
          mapTypeControl: false,
        });
        const marker = new maps.Marker({
          position: center,
          map,
          draggable: true,
        });
        marker.addListener('dragend', () => {
          const pos = marker.getPosition();
          if (pos) onChangeRef.current(pos.lat(), pos.lng());
        });
        map.addListener('click', (e) => {
          if (!e.latLng) return;
          const lat = e.latLng.lat();
          const lng = e.latLng.lng();
          marker.setPosition({ lat, lng });
          onChangeRef.current(lat, lng);
        });
        mapRef.current = map;
        markerRef.current = marker;
        setStatus('ready');
      })
      .catch(() => {
        if (!cancelled) setStatus('error');
      });

    return () => {
      cancelled = true;
    };
    // Intentionally only re-run when the key changes - the map is
    // initialised once, then updated imperatively via marker.setPosition.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey]);

  if (!apiKey) return null;

  return (
    <div className="space-y-2">
      <span className="text-sm font-medium">Pin the exact location (optional)</span>
      {status === 'error' ? (
        <p className="text-sm text-muted-foreground">Map could not be loaded.</p>
      ) : (
        <div
          id={containerId}
          ref={containerRef}
          className="h-56 w-full overflow-hidden rounded-lg border border-border bg-muted"
        />
      )}
      <p className="text-xs text-muted-foreground">
        Click or drag the pin. This is separate from the city/area above and is only shown to buyers
        as a &ldquo;view on map&rdquo; link, never your exact address unless you place the pin there
        yourself.
      </p>
    </div>
  );
}
