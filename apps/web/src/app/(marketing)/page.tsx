/** Next.js route/layout composition for (marketing): page. */
import { CategoryListingRows } from '@/features/marketing';
import {
  CategoryRow,
  ChecksGrid,
  MarketplaceHero,
  Reveal,
  SafetyBanner,
  WhyChooseUs,
  ShoppingHelp,
} from '@/features/marketing';
import { ArrowRight, BadgeCheck, MapPin, Search } from 'lucide-react';
import type { Metadata } from 'next';
import { getLocale } from 'next-intl/server';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Good finds. Greater confidence.',
  description:
    'Buy and sell across Pakistan. Explore real listings, understand seller trust signals, and compare your options with TrustLens shopping help.',
};
export default async function LandingPage() {
  const ur = (await getLocale()) === 'ur';
  const steps = [
    {
      icon: Search,
      n: '01',
      title: ur ? 'اپنی ضرورت ڈھونڈیں' : 'Find your next good thing',
      body: ur
        ? 'قسم، شہر اور بجٹ کے لحاظ سے تلاش کریں۔ اسسٹنٹ سے انتخاب میں مدد لیں۔'
        : 'Search by category, city and budget. Ask the assistant for help choosing.',
      href: '/explore',
      cta: ur ? 'اشتہارات دیکھیں' : 'Start exploring',
    },
    {
      icon: BadgeCheck,
      n: '02',
      title: ur ? 'بیچنے والے کو جانیں' : 'Know who you’re buying from',
      body: ur
        ? 'بیچنے والے کا اسکور اور اس کی وجوہات دیکھیں۔ چیز کی تفصیلات خود پوچھیں۔'
        : 'Read the seller’s trust signals and the reasons behind their score. Ask about the item.',
      href: '/check',
      cta: ur ? 'جانچ کیسے ہوتی ہے' : 'Explore seller checks',
    },
    {
      icon: MapPin,
      n: '03',
      title: ur ? 'دیکھیں، جانچیں، فیصلہ کریں' : 'Meet, inspect, then decide',
      body: ur
        ? 'مناسب عوامی جگہ پر ملیں۔ چیز دیکھیں اور رقم دینے سے پہلے اہم تفصیلات کی تصدیق کریں۔'
        : 'Choose a suitable public place. Inspect the item and confirm important details before paying.',
      href: '/safety',
      cta: ur ? 'محفوظ ملاقات' : 'Plan a safer meetup',
    },
  ];
  return (
    <>
      <MarketplaceHero />
      <CategoryRow />
      <CategoryListingRows />
      <ShoppingHelp />
      <WhyChooseUs />
      <section
        id="how-it-works"
        className="mx-auto max-w-7xl scroll-mt-24 px-5 py-14 sm:px-8 sm:py-16"
      >
        <Reveal>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-brand">
            {ur ? 'چند آسان قدم' : 'A little more confidence'}
          </p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">
            {ur ? 'اچھی خریداری، قدم بہ قدم۔' : 'A better purchase, step by step.'}
          </h2>
        </Reveal>
        <ol className="mt-8 grid gap-5 md:grid-cols-3">
          {steps.map(({ icon: Icon, ...step }, i) => (
            <Reveal as="li" key={step.n} delayMs={i * 60}>
              <div className="h-full rounded-2xl border border-border bg-card p-6">
                <div className="flex items-center justify-between">
                  <Icon className="h-6 w-6 text-brand" strokeWidth={1.5} aria-hidden="true" />
                  <span className="text-xs font-medium tracking-widest text-muted-foreground/60">
                    {step.n}
                  </span>
                </div>
                <h3 className="mt-5 text-base font-semibold">{step.title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{step.body}</p>
                <Link
                  href={step.href}
                  className="mt-5 inline-flex items-center gap-2 text-xs font-semibold text-brand hover:underline"
                >
                  {step.cta}
                  <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
                </Link>
              </div>
            </Reveal>
          ))}
        </ol>
      </section>
      <section id="checks" className="scroll-mt-24 border-t border-border bg-muted/20">
        <div className="mx-auto max-w-7xl px-5 py-12 sm:px-8">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">
                {ur ? 'اسکور کے پیچھے کیا ہے؟' : 'More than a number.'}
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
                {ur
                  ? 'ٹرسٹ اسکور بیچنے والے کے اشاروں کو واضح کرتا ہے۔ یہ چیز کے اصل ہونے، حالت یا محفوظ لین دین کی گارنٹی نہیں۔'
                  : 'Every Trust Score comes with reasons. It reflects seller signals, not a guarantee of product condition, authenticity or a safe transaction.'}
              </p>
            </div>
            <Link
              href="/check"
              className="inline-flex shrink-0 items-center gap-2 text-sm font-semibold text-brand hover:underline"
            >
              {ur ? 'بیچنے والے کی جانچ' : 'Check a seller'}
              <ArrowRight className="h-4 w-4 rtl:rotate-180" />
            </Link>
          </div>
          <details id="explainable" className="mt-6 rounded-xl border border-border bg-card p-5">
            <summary className="cursor-pointer text-sm font-medium">
              {ur ? 'جانچ کی تفصیل دیکھیں' : 'Explore the checks behind the score'}
            </summary>
            <div className="mt-6">
              <ChecksGrid />
            </div>
          </details>
        </div>
      </section>
      <SafetyBanner />
    </>
  );
}
