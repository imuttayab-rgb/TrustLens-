/** Reusable UI rendering and interaction component: HeaderSearch. */
'use client';

import { HeaderLocation } from './HeaderLocation';
import { SmartSearch } from '@/features/assistant';
import {
  LISTING_CATEGORIES,
  MARKETPLACE_ROOTS,
  categoryNode,
  areasForCity,
  withBrowseLocation,
} from '@trustlens/constants';
import { MapPin, Search } from 'lucide-react';
import { useLocale } from 'next-intl';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import styles from './HeaderSearch.module.css';

/** URL-backed search shared by every marketplace screen. No AI call on typing. */
export function HeaderSearch() {
  const isUrdu = useLocale() === 'ur';
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  // Only Browse's parameters are filters; don't copy login or account parameters.
  const base =
    pathname === '/browse'
      ? params.toString()
      : (withBrowseLocation('/', params).split('?')[1] ?? '');
  const search = new URLSearchParams(base);
  const q = search.get('q') ?? '';
  const rawCategory = search.get('category');
  const category =
    rawCategory && (LISTING_CATEGORIES as readonly string[]).includes(rawCategory)
      ? rawCategory
      : null;
  const nodeId = search.get('categoryNodeId');
  const city = search.get('city');
  const rawArea = search.get('area');
  const area = city && rawArea && areasForCity(city).includes(rawArea) ? rawArea : null;
  const hasNearby = search.has('lat') && search.has('lng');
  const radius = Number(search.get('radius') ?? 15);
  const nearby = hasNearby && Number.isFinite(radius) && radius > 0 ? radius : null;
  const [value, setValue] = useState(q);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  useEffect(() => {
    setValue(q);
    setLocationError(null);
  }, [q, pathname]);

  function navigate(next: Record<string, string | null>) {
    const destination = new URLSearchParams(base);
    for (const [key, text] of Object.entries({ q: value.trim() || null, ...next })) {
      if (text) destination.set(key, text);
      else destination.delete(key);
    }
    destination.delete('page');
    router.push(`/browse${destination.size ? `?${destination.toString()}` : ''}`);
  }
  function findNearby() {
    setLocationError(null);
    if (!navigator.geolocation) {
      setLocationError(
        isUrdu
          ? 'مقام دستیاب نہیں۔ اپنا صوبہ اور شہر منتخب کریں۔'
          : 'Location is unavailable. Choose your province and city instead.',
      );
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLocating(false);
        navigate({
          city: null,
          area: null,
          lat: String(coords.latitude),
          lng: String(coords.longitude),
          radius: '15',
        });
      },
      () => {
        setLocating(false);
        setLocationError(
          isUrdu
            ? 'مقام تک رسائی نہیں ہو سکی۔ اپنا صوبہ اور شہر منتخب کریں۔'
            : 'Could not access your location. Choose your province and city instead.',
        );
      },
      { timeout: 10000 },
    );
  }
  return (
    <div className={styles.searchStrip}>
      <form
        role="search"
        aria-label={isUrdu ? 'مارکیٹ پلیس میں تلاش' : 'Marketplace search'}
        className={styles.searchForm}
        onSubmit={(event) => {
          event.preventDefault();
          navigate({});
        }}
      >
        <div className={styles.searchFields}>
          <select
            aria-label={isUrdu ? 'تلاش کی قسم' : 'Search category'}
            value={categoryNode(nodeId)?.parentId ? '' : (nodeId ?? '')}
            onChange={(e) =>
              navigate({ categoryNodeId: e.target.value || null, category: null, facets: null })
            }
            className="h-10 max-w-[150px] rounded-lg border border-input bg-background px-2 text-xs"
          >
            <option value="">{isUrdu ? 'تمام اقسام' : 'All categories'}</option>
            {MARKETPLACE_ROOTS.map((n) => (
              <option key={n.id} value={n.id}>
                {isUrdu ? n.labelUr : n.label}
              </option>
            ))}
          </select>
          <div className={styles.query}>
            <Search aria-hidden="true" />
            <SmartSearch
              value={value}
              onChange={setValue}
              category={category}
              city={city}
              onSelect={(text, suggestedCategory) =>
                navigate({ q: text.trim() || null, category: nodeId ? null : suggestedCategory })
              }
              placeholder={isUrdu ? 'آپ کیا تلاش کر رہے ہیں؟' : 'What are you looking for?'}
              label={isUrdu ? 'اشتہارات تلاش کریں' : 'Search listings'}
              className={styles.searchInput ?? ''}
            />
          </div>
          <HeaderLocation
            city={city}
            area={area}
            nearby={nearby}
            locating={locating}
            locationError={locationError}
            onNearby={findNearby}
            onClearNearby={() => navigate({ lat: null, lng: null, radius: null })}
            onApply={(nextCity, nextArea) =>
              navigate({ city: nextCity, area: nextArea, lat: null, lng: null, radius: null })
            }
          />
        </div>
        <button type="submit" className={`${styles.primary} ${styles.searchButton}`}>
          <Search aria-hidden="true" />
          {isUrdu ? 'تلاش کریں' : 'Search'}
        </button>
      </form>
    </div>
  );
}

export function HeaderSearchFallback() {
  const isUrdu = useLocale() === 'ur';
  return (
    <div className={styles.searchStrip} aria-busy="true" aria-label="Loading marketplace search">
      <div className={styles.searchForm}>
        <div className={styles.searchFields}>
          <div className={styles.query}>
            <Search aria-hidden="true" />
            <span className={styles.placeholder}>
              {isUrdu ? 'آپ کیا تلاش کر رہے ہیں؟' : 'What are you looking for?'}
            </span>
          </div>
          <div className={styles.locationRoot}>
            <div className={styles.locationTrigger}>
              <MapPin aria-hidden="true" />
              {isUrdu ? 'پورا پاکستان' : 'All Pakistan'}
            </div>
          </div>
        </div>
        <button disabled className={`${styles.primary} ${styles.searchButton}`}>
          <Search aria-hidden="true" />
          {isUrdu ? 'تلاش کریں' : 'Search'}
        </button>
      </div>
    </div>
  );
}
