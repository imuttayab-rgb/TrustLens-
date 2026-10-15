/** Guidecards module; defines GuideCards. */
'use client';
import { useLocale } from 'next-intl';
import Link from 'next/link';
import { BookOpen, ArrowRight } from 'lucide-react';
import { GUIDES, type Guide } from './content';
export function GuideCards({ category }: { category?: Guide['category'] }) {
  const ur = useLocale() === 'ur';
  const index = ur ? 1 : 0;
  const items = category
    ? GUIDES.filter((g) => g.category === category || g.category === 'selling')
    : GUIDES;
  return (
    <section className="py-8">
      <div className="mb-5 flex items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{ur ? 'ٹرسٹ لینس رہنمائی' : 'TrustLens guides'}</h2>
        {category && (
          <Link href="/guides" className="text-sm font-semibold text-brand">
            {ur ? 'تمام مضامین' : 'All guides'}
          </Link>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((g) => (
          <Link
            key={g.slug}
            href={`/guides/${g.slug}`}
            className="tl-interactive rounded-2xl border border-border bg-card p-6"
          >
            <BookOpen className="mb-4 h-6 w-6 text-brand" aria-hidden="true" />
            <h3 className="font-semibold">{g.title[index]}</h3>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">{g.intro[index]}</p>
            <span className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-brand">
              {ur ? 'پڑھیں' : 'Read guide'}
              <ArrowRight className="h-4 w-4 rtl:rotate-180" />
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
