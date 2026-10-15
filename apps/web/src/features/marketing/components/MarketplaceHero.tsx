/** Reusable UI rendering and interaction component: MarketplaceHero. */
'use client';

import { useBrowseContext } from '@/features/marketplace';
import { askAssistant } from '@/features/assistant';

import { Button } from '@trustlens/ui';
import {
  ArrowRight,
  BadgeCheck,
  Check,
  MapPin,
  ShieldCheck,
  Sparkles,
  UserCheck,
} from 'lucide-react';
import Link from 'next/link';
import { useLocale } from 'next-intl';

function TrustPreview() {
  const ur = useLocale() === 'ur';
  return (
    <div className="relative mx-auto w-full max-w-[450px] py-5 lg:py-0">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-full bg-brand/10 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="absolute inset-3 rotate-3 rounded-[28px] border border-brand/15 bg-brand/5"
      />
      <div className="relative rounded-[24px] border border-border bg-card p-5 shadow-[0_24px_65px_-35px_hsl(var(--brand)/0.5)] sm:p-7">
        <div className="flex items-center justify-between">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-brand/10 text-brand">
            <ShieldCheck className="h-6 w-6" />
          </span>
          <span className="rounded-full bg-muted px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            {ur ? 'مثالی اسکور' : 'Example score'}
          </span>
        </div>
        <h2 className="mt-5 max-w-xs text-xl font-semibold leading-snug tracking-tight sm:text-2xl">
          {ur ? 'خریدنے سے پہلے، تھوڑا اطمینان۔' : 'A little clarity goes a long way.'}
        </h2>
        <div className="mt-6 flex items-center gap-5">
          <div
            className="relative h-24 w-24 shrink-0"
            role="img"
            aria-label={
              ur ? 'مثالی ٹرسٹ اسکور 92 از 100' : 'Illustrative trust score 92 out of 100'
            }
          >
            <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90" aria-hidden="true">
              <circle cx="50" cy="50" r="43" fill="none" strokeWidth="6" className="stroke-muted" />
              <circle
                cx="50"
                cy="50"
                r="43"
                fill="none"
                strokeWidth="6"
                strokeLinecap="round"
                strokeDasharray="249 271"
                className="stroke-brand"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold tracking-tight">92</span>
              <span className="text-[10px] text-muted-foreground">/ 100</span>
            </div>
          </div>
          <ul className="flex-1 space-y-3 text-xs sm:text-sm">
            {[
              { icon: UserCheck, label: ur ? 'شناخت کی جانچ' : 'Identity checks' },
              { icon: BadgeCheck, label: ur ? 'فون اور ای میل' : 'Phone & email' },
              { icon: ShieldCheck, label: ur ? 'ہر پوائنٹ کی وجہ' : 'See the reasons' },
            ].map(({ icon: Icon, label }) => (
              <li key={label} className="flex items-center gap-2">
                <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="flex-1">{label}</span>
                <Check className="h-3.5 w-3.5 text-brand" aria-hidden="true" />
              </li>
            ))}
          </ul>
        </div>
        <div className="mt-6 border-t border-border pt-4">
          <p className="text-[11px] leading-5 text-muted-foreground">
            {ur
              ? 'بیچنے والے کے اشارے، پروڈکٹ کی گارنٹی نہیں۔'
              : 'Seller signals, not a product guarantee.'}
          </p>
          <Link
            href="/check"
            className="mt-2 inline-flex items-center gap-2 text-xs font-semibold text-brand hover:underline"
          >
            {ur ? 'بیچنے والے کی جانچ کریں' : 'Understand who you’re buying from'}
            <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
          </Link>
        </div>
      </div>
      <button
        type="button"
        onClick={() => askAssistant()}
        className="relative mx-auto -mt-1 flex w-[94%] items-center gap-3 rounded-b-2xl bg-[#102d36] px-4 py-4 text-start text-white shadow-lg transition-colors hover:bg-[#173d47]"
      >
        <Sparkles className="h-5 w-5 shrink-0 text-emerald-300" />
        <span className="flex-1">
          <span className="block text-xs font-semibold">
            {ur ? 'کیا خریدنا بہتر ہوگا؟' : 'Need a second opinion?'}
          </span>
          <span className="mt-0.5 block text-[11px] text-slate-300">
            {ur ? 'اپنا بجٹ ٹرسٹ لینس کو بتائیں۔' : 'Tell TrustLens your budget.'}
          </span>
        </span>
        <ArrowRight className="h-4 w-4 text-emerald-300 rtl:rotate-180" />
      </button>
    </div>
  );
}

export function MarketplaceHero() {
  const context = useBrowseContext();
  const ur = useLocale() === 'ur';
  return (
    <section className="relative isolate border-b border-border/60 bg-gradient-to-b from-brand/[0.025] to-transparent">
      <div
        className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
        aria-hidden="true"
      >
        <div className="absolute -left-14 top-20 h-72 w-72 rounded-full bg-brand/[0.04] blur-3xl" />
        <div className="absolute right-0 top-10 h-96 w-96 rounded-full bg-brand/[0.035] blur-3xl" />
      </div>
      <div className="mx-auto max-w-7xl px-5 pt-6 sm:px-8 sm:pt-8">
        <div className="grid items-center gap-10 py-12 sm:py-16 lg:grid-cols-[1.15fr_1fr] lg:gap-20">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-brand sm:text-xs">
              {ur ? 'بہتر خریدیں۔ سمجھداری سے بیچیں۔' : 'Buy better. Sell smarter.'}
            </p>
            <h1 className="mt-5 text-[2.7rem] font-bold leading-[1.08] tracking-[-0.045em] sm:text-6xl lg:text-[4.2rem]">
              {ur ? 'بہترین انتخاب۔' : 'Good finds.'}
              <br />
              <span className="text-brand">{ur ? 'زیادہ اطمینان۔' : 'Greater confidence.'}</span>
            </h1>
            <p className="mt-5 max-w-lg text-sm leading-7 text-muted-foreground sm:text-base">
              {ur
                ? 'روزمرہ کی ضرورت ہو یا اگلی بڑی خریداری، بیچنے والے کو جانچیں، آپشنز کا موازنہ کریں اور اطمینان سے فیصلہ کریں۔'
                : 'Explore everyday essentials and your next big purchase. Check the seller, compare your options, and decide with clarity.'}
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Button asChild size="lg" className="gap-2 rounded-xl">
                <Link href={context.href('/explore')}>
                  {ur ? 'اشتہارات دیکھیں' : 'Explore listings'}
                  <ArrowRight className="h-4 w-4 rtl:rotate-180" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg" className="gap-2 rounded-xl bg-card">
                <Link href="/check">
                  <ShieldCheck className="h-4 w-4 text-brand" />
                  {ur ? 'بیچنے والے کی جانچ' : 'Check a seller'}
                </Link>
              </Button>
            </div>
            <div className="mt-7 flex flex-wrap gap-x-5 gap-y-2 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <UserCheck className="h-3.5 w-3.5 text-brand" />
                {ur ? 'بیچنے والے کی معلومات' : 'Seller checks'}
              </span>
              <button
                type="button"
                onClick={() => askAssistant()}
                className="flex items-center gap-1.5 hover:text-brand"
              >
                <Sparkles className="h-3.5 w-3.5 text-brand" />
                {ur ? 'خریداری میں مدد' : 'Shopping help'}
              </button>
              <Link href="/safety" className="flex items-center gap-1.5 hover:text-brand">
                <MapPin className="h-3.5 w-3.5 text-brand" />
                SafeMeet
              </Link>
            </div>
          </div>
          <TrustPreview />
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-border/60 py-5 text-xs">
          <span className="me-2 font-medium text-muted-foreground">
            {ur ? 'تجویز کردہ تلاشیں' : 'Suggested searches'}
          </span>
          {[
            { label: 'iPhone Mobile Phones', cat: 'mobiles', q: 'iPhone' },
            { label: 'Samsung Mobile Phones', cat: 'mobiles', q: 'Samsung' },
            { label: 'Honda CD 70', cat: 'vehicles', q: 'CD 70' },
            { label: 'Suzuki Alto', cat: 'vehicles', q: 'Alto' },
            { label: 'Laptops', cat: 'computers', q: 'laptop' },
            { label: 'Houses for Rent', cat: 'property-rent', q: 'house' },
            { label: 'Washing Machines', cat: 'home-appliances', q: 'washing' },
            { label: 'PS5 Consoles', cat: 'electronics', q: 'PS5' },
          ].map((item) => (
            <Link
              key={item.q}
              href={context.href(`/browse?category=${item.cat}&q=${encodeURIComponent(item.q)}`)}
              className="rounded-full border border-border bg-card px-3 py-1.5 text-muted-foreground transition-colors hover:border-brand/30 hover:text-brand"
            >
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
