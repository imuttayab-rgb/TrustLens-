/** Reusable UI rendering and interaction component: HubDiscovery. */
'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useLocale } from 'next-intl';
import { Car, Building2, Home, LandPlot, MapPin } from 'lucide-react';
import { categoryChildren, categoryBrowseHref, productOptions } from '@trustlens/constants';
import { useBrowseContext } from '../browse-context';
const CITIES = [
  'Karachi',
  'Lahore',
  'Islamabad',
  'Rawalpindi',
  'Faisalabad',
  'Multan',
  'Peshawar',
  'Quetta',
];
export function HubDiscovery({
  kind,
  purpose = 'property-sale',
}: {
  kind: 'motors' | 'property';
  purpose?: string;
}) {
  const ur = useLocale() === 'ur';
  const context = useBrowseContext();
  const [tab, setTab] = useState<'make' | 'model' | 'city' | 'budget'>('make');
  const [make, setMake] = useState('Toyota');
  const motor = kind === 'motors';
  const node = motor ? 'vehicles/cars' : purpose;
  const browse = (fields: Record<string, string>) =>
    context.href(`${categoryBrowseHref(node)}&${new URLSearchParams(fields)}`);
  const makes = [
    ...new Set([
      ...productOptions('vehicles/cars', 'make'),
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
    ]),
  ].sort();
  const models = productOptions('vehicles/cars', 'model', make);
  const budgets = motor
    ? [1000000, 2000000, 3000000, 5000000, 10000000]
    : purpose === 'property-rent'
      ? [30000, 60000, 100000, 200000]
      : [5000000, 10000000, 20000000, 50000000];
  return (
    <section
      className="my-8 rounded-2xl border border-border bg-card p-5 sm:p-7"
      aria-label={ur ? 'تلاش کے مزید طریقے' : 'More ways to browse'}
    >
      <h2 className="text-xl font-semibold">
        {motor
          ? ur
            ? 'اپنی پسند کی گاڑی تلاش کریں'
            : 'Find the right car for you'
          : ur
            ? 'قسم کے لحاظ سے پراپرٹی'
            : 'Explore property types'}
      </h2>
      {!motor && (
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {categoryChildren(purpose).map((n) => {
            const Icon = n.id.includes('land')
              ? LandPlot
              : n.id.includes('house')
                ? Home
                : Building2;
            return (
              <Link
                key={n.id}
                href={context.href(categoryBrowseHref(n.id))}
                className="tl-interactive flex min-h-28 flex-col items-center justify-center gap-3 rounded-xl border border-border bg-background p-4 text-center text-sm font-semibold"
              >
                <Icon className="h-8 w-8 text-brand" strokeWidth={1.5} aria-hidden="true" />
                {ur ? n.labelUr : n.label}
              </Link>
            );
          })}
        </div>
      )}
      <div
        className="mt-5 flex flex-wrap gap-2 border-b border-border pb-3"
        aria-label={ur ? 'تلاش کا طریقہ' : 'Browse by'}
      >
        {(motor ? ['make', 'model', 'city', 'budget'] : ['city', 'budget']).map((t) => (
          <button
            key={t}
            type="button"
            aria-pressed={(motor ? tab : tab === 'budget' ? 'budget' : 'city') === t}
            onClick={() => setTab(t as typeof tab)}
            className={`min-h-10 rounded-lg px-4 text-sm font-medium ${(motor ? tab : tab === 'budget' ? 'budget' : 'city') === t ? 'bg-brand/10 text-brand' : 'hover:bg-muted'}`}
          >
            {
              (ur
                ? { make: 'کمپنی', model: 'ماڈل', city: 'شہر', budget: 'بجٹ' }
                : { make: 'Make', model: 'Model', city: 'City', budget: 'Budget' })[t as typeof tab]
            }
          </button>
        ))}
      </div>
      {motor && tab === 'make' ? (
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          {makes.map((m) => (
            <Link
              key={m}
              href={browse({ facets: JSON.stringify({ make: m }) })}
              className="tl-interactive flex min-h-24 flex-col items-center justify-center gap-2 rounded-xl border border-border bg-background p-3 text-sm"
            >
              <Car className="h-7 w-7 text-brand" aria-hidden="true" />
              <span className="text-center font-semibold">{m}</span>
            </Link>
          ))}
        </div>
      ) : motor && tab === 'model' ? (
        <>
          <label className="mt-4 block max-w-xs text-sm">
            {ur ? 'کمپنی منتخب کریں' : 'Choose a make'}
            <select
              value={make}
              onChange={(e) => setMake(e.target.value)}
              className="mt-2 h-11 w-full rounded-lg border border-input bg-background px-3"
            >
              {makes.map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </label>
          <div className="mt-4 flex flex-wrap gap-3">
            {models.map((m) => (
              <Link
                key={m}
                href={browse({ facets: JSON.stringify({ make, model: m }) })}
                className="tl-interactive rounded-xl border border-border px-4 py-3 text-sm"
              >
                {m}
              </Link>
            ))}
            {!models.length && (
              <Link
                href={browse({ facets: JSON.stringify({ make }) })}
                className="text-sm text-brand underline"
              >
                {ur ? 'اس کمپنی کے تمام اشتہارات' : 'Browse all listings from this make'}
              </Link>
            )}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            {ur
              ? 'اپنا ماڈل اوپر تلاش میں بھی لکھ سکتے ہیں۔'
              : 'You can also type an unlisted model in the search form above.'}
          </p>
        </>
      ) : tab === 'budget' ? (
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {budgets.map((max) => (
            <Link
              key={max}
              href={browse({ maxPrice: String(max) })}
              className="tl-interactive rounded-xl border border-border p-4 text-center text-sm font-semibold"
            >
              {ur ? 'زیادہ سے زیادہ' : 'Up to'}
              <span className="mt-1 block">PKR {max.toLocaleString('en-PK')}</span>
            </Link>
          ))}
        </div>
      ) : (
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {CITIES.map((city) => (
            <Link
              key={city}
              href={browse({ city })}
              className="tl-interactive flex items-center gap-2 rounded-xl border border-border p-4 text-sm"
            >
              <MapPin className="h-4 w-4 text-brand" aria-hidden="true" />
              {city}
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
