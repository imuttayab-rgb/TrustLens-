'use client';

import { stagger, usePrefersReducedMotion } from '@/lib/motion';
import { Ambient, Button, cn } from '@trustlens/ui';
import { ArrowRight, Eye, Lock, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { ScorePreview } from './ScorePreview';

const ASSURANCES = [
  { icon: Sparkles, label: 'AI-assisted' },
  { icon: Eye, label: 'Every reason shown' },
  { icon: Lock, label: 'Documents deleted' },
] as const;

export function Hero() {
  const reduced = usePrefersReducedMotion();
  /** Entrance delay for the nth item in the hero's arrival sequence. */
  const at = (index: number) => (reduced ? undefined : stagger(index, 90, 60));

  return (
    <section className="relative overflow-hidden">
      <Ambient intensity="full" />

      <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-14 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.02fr)] lg:gap-14 lg:pt-20">
        <div>
          <span
            className={cn(
              'inline-flex items-center gap-2 rounded-full border border-brand/25 bg-brand/10 px-3 py-1 text-xs font-semibold tracking-wide text-brand',
              !reduced && 'animate-fade-up',
            )}
            style={at(0)}
          >
            <Sparkles className="h-3 w-3" aria-hidden="true" />
            Seller verification, explained
          </span>

          <h1 className="mt-5 text-[2.6rem] font-extrabold leading-[1.04] tracking-tight sm:text-6xl">
            <span className={cn('block', !reduced && 'animate-fade-up')} style={at(1)}>
              Know your seller.
            </span>
            <span className={cn('block', !reduced && 'animate-fade-up')} style={at(2)}>
              Trade with{' '}
              <span className="bg-gradient-to-r from-brand to-brand-2 bg-clip-text text-transparent">
                confidence
              </span>
              .
            </span>
          </h1>

          <p
            className={cn(
              'mt-5 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg',
              !reduced && 'animate-fade-up',
            )}
            style={at(3)}
          >
            TrustLens checks a seller&apos;s ID, phone, email, device and listings, then gives you
            one score out of 100 — and tells you exactly which check earned or cost each point.
          </p>

          <div
            className={cn('mt-8 flex flex-wrap items-center gap-3', !reduced && 'animate-fade-up')}
            style={at(4)}
          >
            <Button
              asChild
              size="lg"
              className="group bg-gradient-to-r from-brand to-brand-2 font-semibold text-[hsl(var(--background))] shadow-[0_10px_36px_-12px_hsl(var(--brand)/0.8)] transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]"
            >
              <Link href="/check">
                Check a seller
                <ArrowRight
                  className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1"
                  aria-hidden="true"
                />
              </Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="transition-colors hover:border-brand/40"
            >
              <Link href="/register">Get verified as a seller</Link>
            </Button>
          </div>

          <ul
            className={cn(
              'mt-8 flex flex-wrap items-center gap-x-6 gap-y-3',
              !reduced && 'animate-fade-up',
            )}
            style={at(5)}
          >
            {ASSURANCES.map((item) => {
              const Icon = item.icon;
              return (
                <li
                  key={item.label}
                  className="flex items-center gap-2 text-sm text-muted-foreground"
                >
                  <Icon className="h-3.5 w-3.5 text-brand" aria-hidden="true" />
                  {item.label}
                </li>
              );
            })}
          </ul>
        </div>

        <div
          className={cn(!reduced && 'animate-fade-up')}
          style={reduced ? undefined : stagger(3, 90, 140)}
        >
          <ScorePreview />
        </div>
      </div>
    </section>
  );
}
