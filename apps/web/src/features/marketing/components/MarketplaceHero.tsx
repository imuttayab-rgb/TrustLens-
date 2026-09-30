'use client';

import { stagger, useCountUp, useInView, usePrefersReducedMotion } from '@/lib/motion';
import { Ambient, Button, cn } from '@trustlens/ui';
import { PAKISTAN_CITIES } from '@trustlens/constants';
import {
  ArrowRight,
  BadgeCheck,
  IdCard,
  Lock,
  Mail,
  Phone,
  ScanFace,
  Search,
  ShieldCheck,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useState } from 'react';

const CHECKLIST = [
  { icon: IdCard, key: 'identity' },
  { icon: Phone, key: 'phone' },
  { icon: Mail, key: 'email' },
  { icon: ScanFace, key: 'liveId', badge: 'New' },
] as const;

function SearchBar({ className }: { className?: string }) {
  const t = useTranslations('Home');
  const router = useRouter();
  const [q, setQ] = useState('');
  const [city, setCity] = useState('');
  const [focused, setFocused] = useState(false);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const params = new URLSearchParams();
    if (q.trim()) params.set('q', q.trim());
    if (city) params.set('city', city);
    router.push(`/browse${params.toString() ? `?${params}` : ''}`);
  }

  return (
    <form
      onSubmit={submit}
      className={cn(
        'flex flex-col gap-2 rounded-xl border bg-card p-2 shadow-sm transition-[box-shadow,border-color] duration-300 sm:flex-row sm:items-center',
        focused
          ? 'border-brand/40 shadow-[0_0_0_4px_hsl(var(--brand)/0.1)]'
          : 'border-border hover:border-foreground/20',
        className,
      )}
    >
      <div className="flex flex-1 items-center gap-2 px-2">
        <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={t('searchPlaceholder')}
          aria-label={t('searchPlaceholder')}
          className="h-10 w-full min-w-0 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
      <div className="h-px w-full bg-border sm:h-6 sm:w-px" aria-hidden="true" />
      <select
        value={city}
        onChange={(event) => setCity(event.target.value)}
        aria-label={t('locationLabel')}
        className="h-10 rounded-lg border border-transparent bg-transparent px-3 text-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:w-44"
      >
        <option value="">{t('allPakistan')}</option>
        {PAKISTAN_CITIES.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
      <Button
        type="submit"
        className="group h-10 gap-2 transition-transform duration-200 hover:scale-[1.02] active:scale-[0.98] sm:w-auto"
      >
        <Search className="h-4 w-4 transition-transform group-hover:scale-110" aria-hidden="true" />
        {t('search')}
      </Button>
    </form>
  );
}

function TrustScoreCard() {
  const t = useTranslations('Home');
  const { ref, inView } = useInView<HTMLDivElement>('-10% 0px');
  const reduced = usePrefersReducedMotion();
  const score = useCountUp(92, inView);
  const shown = Math.round(score);

  const RADIUS = 46;
  const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
  const offset = CIRCUMFERENCE * (1 - (reduced ? 92 : score) / 100);

  return (
    <div
      ref={ref}
      className={cn(
        'relative overflow-hidden rounded-2xl border border-border bg-card p-5 shadow-[0_1px_2px_hsl(var(--foreground)/0.04),0_20px_50px_-24px_hsl(var(--brand)/0.35)] transition-transform duration-500',
        !reduced && inView && 'animate-fade-up',
        !reduced && !inView && 'opacity-0',
      )}
    >
      <p className="text-sm font-semibold">{t('safetyPriority')}</p>

      <div className="mt-4 flex items-center gap-4">
        <div className="relative shrink-0" style={{ width: 112, height: 112 }}>
          <svg
            width={112}
            height={112}
            viewBox="0 0 112 112"
            role="img"
            aria-label={`Trust Score ${shown} out of 100, low risk`}
            className="-rotate-90"
          >
            <circle
              cx={56}
              cy={56}
              r={RADIUS}
              fill="none"
              strokeWidth={10}
              className="stroke-muted"
            />
            <circle
              cx={56}
              cy={56}
              r={RADIUS}
              fill="none"
              strokeWidth={10}
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={offset}
              className="stroke-risk-low"
              style={{ transition: reduced ? 'none' : 'stroke-dashoffset 100ms linear' }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-extrabold tabular-nums leading-none text-risk-low">
              {shown}
            </span>
            <span className="mt-0.5 text-[10px] text-muted-foreground">out of 100</span>
          </div>
          {!reduced && inView && (
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 animate-sheen bg-gradient-to-r from-transparent via-white/20 to-transparent"
            />
          )}
        </div>

        <div className="min-w-0 flex-1 space-y-1.5">
          {CHECKLIST.map((item, index) => {
            const Icon = item.icon;
            return (
              <div
                key={item.key}
                style={inView && !reduced ? stagger(index, 90, 300) : undefined}
                className={cn(
                  'flex items-center gap-2 rounded-md px-1 py-1 text-sm transition-colors hover:bg-muted/60',
                  !reduced && inView && 'animate-fade-up',
                  !reduced && !inView && 'opacity-0',
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="min-w-0 flex-1 truncate text-muted-foreground">
                  {t(`checklist.${item.key}`)}
                </span>
                {'badge' in item && (
                  <span className="shrink-0 rounded-full bg-brand/15 px-1.5 py-0.5 text-[10px] font-semibold text-brand">
                    {item.badge}
                  </span>
                )}
                <span
                  className={cn(
                    'grid h-4 w-4 shrink-0 place-items-center rounded-full bg-risk-low/15',
                    inView && !reduced && 'animate-pop-in',
                  )}
                  style={inView && !reduced ? stagger(index, 90, 420) : undefined}
                >
                  <BadgeCheck className="h-3 w-3 text-risk-low" aria-hidden="true" />
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <p className="mt-3 text-center text-xs font-semibold uppercase tracking-wide text-risk-low">
        {t('lowRisk')}
      </p>
      <p className="mt-1 text-center text-xs text-muted-foreground">{t('scoreCaption')}</p>

      <div className="mt-4 flex items-center justify-between border-t border-border/70 pt-3">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Lock className="h-3 w-3" aria-hidden="true" />
          {t('dataPromise')}
        </p>
        <Link
          href="/check"
          className="group shrink-0 text-xs font-medium text-primary underline-offset-4 hover:underline"
        >
          {t('howItWorks')}
          <ArrowRight
            className="ml-0.5 inline h-3 w-3 transition-transform group-hover:translate-x-0.5"
            aria-hidden="true"
          />
        </Link>
      </div>
    </div>
  );
}

export function MarketplaceHero() {
  const t = useTranslations('Home');
  const reduced = usePrefersReducedMotion();
  const at = (index: number) => (reduced ? undefined : stagger(index, 90, 40));

  return (
    <section className="relative overflow-hidden border-b border-border/70 bg-muted/30">
      <Ambient intensity="full" />

      {/* Dotted grid, top-left - purely atmospheric, matches the reference
          design's texture without competing with the search bar above it. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-8 -top-8 h-48 w-48 opacity-[0.35] [background-image:radial-gradient(hsl(var(--brand)/0.35)_1.5px,transparent_1.5px)] [background-size:18px_18px] [mask-image:radial-gradient(circle,#000_0%,transparent_75%)]"
      />

      {/* A huge, near-invisible shield watermark behind the trust card -
          reinforces "safety" as the page's own background texture. */}
      <ShieldCheck
        aria-hidden="true"
        strokeWidth={1}
        className="pointer-events-none absolute right-[-4rem] top-1/2 hidden h-[26rem] w-[26rem] -translate-y-1/2 text-brand/[0.06] sm:block"
      />

      <div className="relative mx-auto max-w-7xl px-5 py-10 sm:px-8 sm:py-14">
        <div className={cn(!reduced && 'animate-fade-up')} style={at(0)}>
          <SearchBar />
        </div>

        <div className="mt-10 grid items-center gap-10 lg:grid-cols-[1.1fr_1fr] lg:gap-14">
          <div>
            <h1
              className={cn(
                'text-4xl font-extrabold tracking-tight sm:text-5xl',
                !reduced && 'animate-fade-up',
              )}
              style={at(1)}
            >
              {t('headline')}
            </h1>
            <p
              className={cn(
                'mt-4 max-w-md text-base leading-relaxed text-muted-foreground sm:text-lg',
                !reduced && 'animate-fade-up',
              )}
              style={at(2)}
            >
              {t('subheadline')}
            </p>
            <div className={cn('mt-7', !reduced && 'animate-fade-up')} style={at(3)}>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="group gap-2 border-brand/30 transition-colors hover:border-brand/50 hover:bg-brand/5"
              >
                <Link href="/check">
                  <ShieldCheck className="h-4 w-4 text-brand" aria-hidden="true" />
                  {t('checkSeller')}
                  <ArrowRight
                    className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1"
                    aria-hidden="true"
                  />
                </Link>
              </Button>
            </div>
          </div>

          <div className={cn(!reduced && 'animate-fade-up')} style={at(2)}>
            <TrustScoreCard />
          </div>
        </div>
      </div>
    </section>
  );
}
