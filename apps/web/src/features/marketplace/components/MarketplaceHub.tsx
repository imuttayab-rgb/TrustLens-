/** Reusable UI rendering and interaction component: MarketplaceHub. */
'use client';
import { useState, useEffect } from 'react';
import { useLocale } from 'next-intl';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { CityPicker } from '@/features/location';
import { ListingRow } from '@/features/marketing';
import {
  categoryChildren,
  categoryBrowseHref,
  categoryLabel,
  PAKISTAN_CITIES,
  productOptions,
  categoryOptionLabel,
} from '@trustlens/constants';
import { Dealers } from './Dealers';
import { HubDiscovery } from './HubDiscovery';
import { useBrowseContext } from '../browse-context';
import { GuideCards } from '@/features/guides';
const MAKES = [
  'Suzuki',
  'Toyota',
  'Honda',
  'Daihatsu',
  'Nissan',
  'Mitsubishi',
  'Hyundai',
  'Kia',
  'Changan',
  'MG',
  'Haval',
  'Audi',
  'BMW',
  'Mercedes-Benz',
  'Peugeot',
  'Proton',
  'DFSK',
  'FAW',
  'Isuzu',
  'Other',
];
export function MarketplaceHub({ kind }: { kind: 'motors' | 'property' }) {
  const ur = useLocale() === 'ur';
  const context = useBrowseContext();
  const motor = kind === 'motors';
  const router = useRouter();
  const [purpose, setPurpose] = useState<'property-sale' | 'property-rent'>('property-sale');
  const [node, setNode] = useState(motor ? 'vehicles/cars' : 'property-sale/houses');
  const [city, setCity] = useState(context.city ?? '');
  useEffect(() => setCity(context.city ?? ''), [context.city]);
  const [make, setMake] = useState('');
  const [model, setModel] = useState('');
  const [min, setMin] = useState('');
  const [max, setMax] = useState('');
  const [year, setYear] = useState('');
  const [mileage, setMileage] = useState('');
  const [area, setArea] = useState('');
  const [unit, setUnit] = useState('Marla');
  const [error, setError] = useState('');
  const root = motor ? 'vehicles' : purpose;
  const input = 'h-12 w-full rounded-xl border border-input bg-background px-3 text-sm';
  function search(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    const nmin = min.trim() ? Number(min) : null,
      nmax = max.trim() ? Number(max) : null;
    const numeric = [nmin, nmax, ...(motor ? [year, mileage] : [area]).filter(Boolean).map(Number)];
    if (
      numeric.some((n) => n !== null && (!Number.isFinite(n) || n < 0)) ||
      (nmin !== null && nmax !== null && nmin > nmax)
    ) {
      setError(ur ? 'بجٹ اور عددی حدود درست کریں۔' : 'Check your budget and numeric ranges.');
      return;
    }
    if (year && (Number(year) < 1900 || Number(year) > 2100 || !Number.isInteger(Number(year)))) {
      setError(ur ? 'سال 1900 سے 2100 کے درمیان درج کریں۔' : 'Enter a year between 1900 and 2100.');
      return;
    }
    const p = new URLSearchParams({ categoryNodeId: node });
    if (city) p.set('city', city);
    if (nmin !== null) p.set('minPrice', String(nmin));
    if (nmax !== null) p.set('maxPrice', String(nmax));
    const facets: Record<string, unknown> = {};
    if (motor) {
      if (make) facets.make = make;
      if (model.trim()) facets.model = model.trim();
      if (year) facets.year = { min: Number(year) };
      if (mileage) facets.mileage = { max: Number(mileage) };
    } else if (area) {
      facets.area = { min: Number(area) };
      facets.area_unit = unit;
    }
    if (Object.keys(facets).length) p.set('facets', JSON.stringify(facets));
    router.push(`/browse?${p}`);
  }
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
      <section className="relative overflow-hidden rounded-3xl border border-border bg-card p-6 sm:p-10">
        <div className="grid items-center gap-8 lg:grid-cols-[1.2fr_.8fr]">
          <div>
            <p className="text-sm font-semibold text-brand">
              TrustLens {motor ? 'Motors' : 'Property'}
            </p>
            <h1 className="mt-3 max-w-xl text-3xl font-semibold tracking-tight sm:text-4xl">
              {motor
                ? ur
                  ? 'اگلا سفر، بہتر انتخاب۔'
                  : 'Your next journey starts here.'
                : ur
                  ? 'اپنی اگلی جگہ تلاش کریں۔'
                  : 'Find a place for your next chapter.'}
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-6 text-muted-foreground">
              {motor
                ? ur
                  ? 'اصل اشتہارات، واضح تفصیلات اور بیچنے والے کی پروفائل ایک جگہ۔'
                  : 'Explore current listings, compare specifications and get to know the person selling.'
                : ur
                  ? 'خرید یا کرایہ—مقام، رقبے اور بجٹ کے مطابق تلاش کریں۔'
                  : 'Buy or rent. Compare location, area and budget, then connect through TrustLens messaging.'}
            </p>
          </div>
          <div className="hidden h-48 items-center justify-center rounded-2xl bg-brand/5 lg:flex">
            <img
              src={`/images/categories/${motor ? 'vehicles' : purpose}.webp`}
              alt=""
              width={256}
              height={256}
              className="h-52 w-64 object-contain"
            />
          </div>
        </div>
        {!motor && (
          <div
            className="mt-6 flex w-fit gap-1 rounded-xl border border-border p-1"
            aria-label="Property purpose"
          >
            {(['property-sale', 'property-rent'] as const).map((p) => (
              <button
                key={p}
                type="button"
                aria-pressed={purpose === p}
                onClick={() => {
                  setPurpose(p);
                  setNode(`${p}/houses`);
                }}
                className={`rounded-lg px-6 py-2 text-sm font-semibold ${purpose === p ? 'bg-primary text-primary-foreground' : ''}`}
              >
                {p === 'property-sale' ? (ur ? 'خریدیں' : 'Buy') : ur ? 'کرایہ' : 'Rent'}
              </button>
            ))}
          </div>
        )}
        <form onSubmit={search} className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="space-y-1 text-xs">
            <span>{ur ? 'قسم' : 'Listing type'}</span>
            <select
              value={node}
              onChange={(e) => {
                setNode(e.target.value);
                setMake('');
                setModel('');
                setYear('');
                setMileage('');
              }}
              className={input}
            >
              {categoryChildren(root)
                .filter((n) =>
                  motor
                    ? [
                        'vehicles/cars',
                        'vehicles/buses-vans-trucks',
                        'vehicles/rickshaw-chingchi',
                        'vehicles/other-vehicles',
                      ].includes(n.id)
                    : true,
                )
                .map((n) => (
                  <option key={n.id} value={n.id}>
                    {ur ? n.labelUr : n.label}
                  </option>
                ))}
            </select>
          </label>
          <label className="space-y-1 text-xs">
            <span>{ur ? 'شہر' : 'City'}</span>
            <CityPicker
              value={city}
              onChange={setCity}
              cities={PAKISTAN_CITIES}
              placeholder={ur ? 'پورا پاکستان' : 'All Pakistan'}
              className={input}
            />
          </label>
          {motor ? (
            <>
              <label className="space-y-1 text-xs">
                <span>{ur ? 'کمپنی' : 'Make'}</span>
                <select
                  value={make}
                  onChange={(e) => {
                    setMake(e.target.value);
                    setModel('');
                  }}
                  className={input}
                >
                  <option value="">{ur ? 'تمام کمپنیاں' : 'Any make'}</option>
                  {MAKES.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1 text-xs">
                <span>{ur ? 'ماڈل' : 'Model'}</span>
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  maxLength={80}
                  placeholder={ur ? 'مثلاً Corolla' : 'e.g. Corolla'}
                  list="hub-model-options"
                  className={input}
                />
                <datalist id="hub-model-options">
                  {productOptions(node, 'model', make).map((m) => (
                    <option key={m} value={m} />
                  ))}
                </datalist>
              </label>
            </>
          ) : (
            <>
              <label className="space-y-1 text-xs">
                <span>{ur ? 'کم سے کم رقبہ' : 'Minimum area'}</span>
                <input
                  inputMode="decimal"
                  value={area}
                  onChange={(e) => setArea(e.target.value)}
                  className={input}
                />
              </label>
              <label className="space-y-1 text-xs">
                <span>{ur ? 'رقبے کی اکائی' : 'Area unit'}</span>
                <select value={unit} onChange={(e) => setUnit(e.target.value)} className={input}>
                  {['Marla', 'Kanal', 'Square feet', 'Square yards', 'Square metres', 'Acres'].map(
                    (u) => (
                      <option key={u} value={u}>
                        {categoryOptionLabel(u, ur)}
                      </option>
                    ),
                  )}
                </select>
              </label>
            </>
          )}
          <label className="space-y-1 text-xs">
            <span>{ur ? 'کم سے کم بجٹ (روپے)' : 'Minimum budget (PKR)'}</span>
            <input
              inputMode="decimal"
              value={min}
              onChange={(e) => setMin(e.target.value)}
              className={input}
            />
          </label>
          <label className="space-y-1 text-xs">
            <span>{ur ? 'زیادہ سے زیادہ بجٹ (روپے)' : 'Maximum budget (PKR)'}</span>
            <input
              inputMode="decimal"
              value={max}
              onChange={(e) => setMax(e.target.value)}
              className={input}
            />
          </label>
          {motor && (
            <>
              <label className="space-y-1 text-xs">
                <span>{ur ? 'ماڈل سال، اس کے بعد' : 'Model year from'}</span>
                <input
                  inputMode="numeric"
                  value={year}
                  onChange={(e) => setYear(e.target.value)}
                  className={input}
                />
              </label>
              <label className="space-y-1 text-xs">
                <span>{ur ? 'زیادہ سے زیادہ کلومیٹر' : 'Maximum mileage (km)'}</span>
                <input
                  inputMode="numeric"
                  value={mileage}
                  onChange={(e) => setMileage(e.target.value)}
                  className={input}
                />
              </label>
            </>
          )}
          {error && (
            <p role="alert" className="text-sm text-destructive sm:col-span-2 lg:col-span-4">
              {error}
            </p>
          )}
          <button
            type="submit"
            className="h-12 rounded-xl bg-primary px-6 text-sm font-semibold text-primary-foreground sm:col-span-2 lg:col-span-4"
          >
            {ur ? 'اشتہارات تلاش کریں' : 'Search listings'}
          </button>
        </form>
      </section>
      <nav aria-label="Browse related categories" className="my-8 flex flex-wrap gap-3">
        {categoryChildren(root).map((n) => (
          <Link
            key={n.id}
            href={context.href(categoryBrowseHref(n.id))}
            className="tl-interactive rounded-full border border-border bg-card px-4 py-2.5 text-sm"
          >
            {ur ? n.labelUr : n.label}
          </Link>
        ))}
      </nav>
      <HubDiscovery kind={kind} purpose={purpose} />
      <ListingRow
        nodeId={motor ? 'vehicles/cars' : purpose}
        title={
          motor
            ? ur
              ? 'تازہ گاڑیوں کے اشتہارات'
              : 'Latest cars'
            : ur
              ? 'تازہ پراپرٹی اشتہارات'
              : 'Latest property listings'
        }
      />
      {motor ? (
        <>
          <Dealers />
          <ListingRow nodeId="bikes/motorcycles" />
          <ListingRow nodeId="vehicles/spare-parts" />
        </>
      ) : (
        <>
          {categoryChildren(purpose).map((n) => (
            <ListingRow key={n.id} nodeId={n.id} title={categoryLabel(n.id, ur)} />
          ))}
        </>
      )}
      <GuideCards category={kind} />
      <section className="my-8 rounded-2xl border border-border bg-muted/20 p-6">
        <h2 className="text-xl font-semibold">
          {ur ? 'پہلے موازنہ، پھر رابطہ' : 'Compare first. Connect with confidence.'}
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
          {ur
            ? 'تفصیلات اور قیمت کا موازنہ کریں، نامعلوم باتیں پوچھیں اور بیچنے والے کی پروفائل دیکھیں۔ ٹرسٹ اسکور چیز کی حالت کی ضمانت نہیں۔'
            : 'Compare the price and stated details, ask about anything missing, and open the seller’s profile. A trust score describes seller signals; it does not certify the item or property.'}
        </p>
        <Link
          href="/safety"
          className="mt-4 inline-block text-sm font-semibold text-brand underline"
        >
          {ur ? 'حفاظتی رہنمائی' : 'Read safety guidance'}
        </Link>
      </section>
    </div>
  );
}
