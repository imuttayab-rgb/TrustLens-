/** Reusable UI rendering and interaction component: Dealers. */
'use client';
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { profileRequest } from '@/features/profile';
import { ProfileAvatar } from '@/features/profile';
import { CityPicker } from '@/features/location';
import { PAKISTAN_CITIES } from '@trustlens/constants';
import { useBrowseContext } from '../browse-context';
import Link from 'next/link';
import { useLocale } from 'next-intl';
type Dealer = {
  handle: string;
  displayName: string;
  city: string | null;
  activeListings: number;
  profileUrl: string;
  photoUrl: string;
};
export function Dealers({ directory = false }: { directory?: boolean }) {
  const ur = useLocale() === 'ur';
  const context = useBrowseContext();
  const [city, setCity] = useState(context.city ?? '');
  const [query, setQuery] = useState(''),
    [debounced, setDebounced] = useState('');
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(query);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    setCity(context.city ?? '');
    setOffset(0);
  }, [context.city]);
  const result = useQuery<Dealer[]>({
    queryKey: ['marketplace', 'motor-dealers', city, debounced, offset, directory],
    staleTime: 60000,
    queryFn: ({ signal }) =>
      profileRequest(
        `/public/motor-dealers?${new URLSearchParams({ city, q: debounced, offset: String(offset), limit: String(directory ? 13 : 4) })}`,
        { signal },
      ),
  });
  const items = result.data?.slice(0, directory ? 12 : 4) ?? [];
  return (
    <section className="py-7">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xl font-semibold">
          {ur ? 'تصدیق شدہ کاروباری فروخت کنندگان' : 'Verified business sellers'}
        </h2>
        {!directory && (
          <Link href={context.href('/motors/dealers')} className="text-sm font-semibold text-brand">
            {ur ? 'تمام ڈیلرز' : 'All dealers'}
          </Link>
        )}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        {ur
          ? 'تصدیق شدہ کاروباری پروفائلز جن کے فعال موٹرز اشتہارات موجود ہیں۔ ترتیب ادائیگی پر مبنی نہیں۔'
          : 'Approved business profiles with active motor listings, ordered by active inventory. This is not a paid ranking.'}
      </p>
      {directory && (
        <div className="my-5 grid gap-4 sm:grid-cols-2">
          <label className="text-sm">
            {ur ? 'نام سے تلاش' : 'Search by name'}
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              maxLength={80}
              className="mt-2 h-11 w-full rounded-lg border border-input bg-background px-3"
            />
          </label>
          <div className="text-sm">
            <span>{ur ? 'شہر' : 'City'}</span>
            <div className="mt-2">
              <CityPicker
                value={city}
                onChange={(v) => {
                  setCity(v);
                  setOffset(0);
                }}
                cities={PAKISTAN_CITIES}
                placeholder={ur ? 'پورا پاکستان' : 'All Pakistan'}
                className="h-11 w-full rounded-lg border border-input bg-background px-3"
              />
            </div>
          </div>
        </div>
      )}
      {result.isPending ? (
        <p role="status" className="py-6 text-sm text-muted-foreground">
          {ur ? 'فروخت کنندگان لوڈ ہو رہے ہیں…' : 'Loading sellers…'}
        </p>
      ) : result.isError ? (
        <button
          type="button"
          className="mt-4 text-sm text-brand underline"
          onClick={() => void result.refetch()}
        >
          {ur ? 'لوڈ نہیں ہوا، دوبارہ کوشش کریں' : 'Could not load sellers. Try again.'}
        </button>
      ) : !items.length ? (
        <p className="mt-4 rounded-xl border border-dashed border-border p-5 text-sm text-muted-foreground">
          {ur
            ? 'اس تلاش میں ابھی کوئی موزوں کاروباری فروخت کنندہ نہیں ملا۔'
            : 'No eligible business sellers match this search yet.'}
        </p>
      ) : (
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {items.map((d) => (
            <Link
              key={d.handle}
              href={d.profileUrl}
              className="tl-interactive rounded-xl border border-border bg-card p-5"
            >
              <ProfileAvatar src={d.photoUrl} name={d.displayName} size={56} />
              <p className="mt-4 font-semibold">{d.displayName}</p>
              <p className="mt-2 text-sm text-muted-foreground">{d.city}</p>
              <p className="mt-3 text-xs text-brand">
                {d.activeListings} {ur ? 'فعال اشتہارات' : 'active listings'}
              </p>
            </Link>
          ))}
        </div>
      )}
      {directory && (offset > 0 || (result.data?.length ?? 0) > 12) && (
        <nav
          className="mt-5 flex justify-between"
          aria-label={ur ? 'ڈیلرز کے صفحات' : 'Dealer pages'}
        >
          <button
            type="button"
            disabled={offset === 0 || result.isFetching}
            onClick={() => setOffset((v) => Math.max(0, v - 12))}
            className="rounded-lg border border-border px-4 py-2 disabled:opacity-40"
          >
            {ur ? 'پچھلا' : 'Previous'}
          </button>
          <button
            type="button"
            disabled={(result.data?.length ?? 0) <= 12 || result.isFetching}
            onClick={() => setOffset((v) => v + 12)}
            className="rounded-lg border border-border px-4 py-2 disabled:opacity-40"
          >
            {ur ? 'اگلا' : 'Next'}
          </button>
        </nav>
      )}
    </section>
  );
}
