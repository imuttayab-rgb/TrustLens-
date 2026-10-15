/** Next.js route/layout composition for (auth-split): AuthMarketingPanel. */
'use client';

import { stagger, usePrefersReducedMotion } from '@/lib/motion';
import { Ambient } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { MapPin, MessageCircle, ScanFace, ShieldCheck } from 'lucide-react';
import Image from 'next/image';

/**
 * The same four features the homepage's "Why choose us" section shows
 * (`Home.features.*`), copied rather than wired through next-intl - this
 * surface (login/register) is English-only today, unlike the marketing
 * site, so pulling in the translation layer for one panel would be its own
 * inconsistency.
 */
const FEATURES = [
  {
    icon: ShieldCheck,
    title: 'Explainable Trust Score',
    body: 'Clear score based on verified data and behaviour.',
  },
  {
    icon: ScanFace,
    title: 'Live identity verification',
    body: 'Sellers verify identity with live ID checks.',
  },
  {
    icon: MessageCircle,
    title: 'Safe in-app chat',
    body: 'Stay protected with secure messaging.',
  },
  {
    icon: MapPin,
    title: 'Platform-curated SafeMeet',
    body: 'Meet in public, verified locations.',
  },
] as const;

export function AuthMarketingPanel() {
  const reduced = usePrefersReducedMotion();

  return (
    <div className="relative hidden overflow-hidden bg-muted/30 p-10 lg:flex lg:flex-col lg:justify-center xl:p-16">
      <Ambient intensity="full" />

      <div className="relative mx-auto w-full max-w-md">
        <h1
          className={cn(
            'text-3xl font-bold tracking-tight xl:text-4xl',
            !reduced && 'animate-fade-up',
          )}
        >
          Join Pakistan&apos;s trusted marketplace
        </h1>
        <p
          style={!reduced ? stagger(1, 90) : undefined}
          className={cn('mt-3 text-base text-muted-foreground', !reduced && 'animate-fade-up')}
        >
          Buy with confidence. Sell with trust.
        </p>

        <div
          style={!reduced ? stagger(2, 90) : undefined}
          className={cn(
            'relative mx-auto mt-10 aspect-square w-full max-w-sm',
            !reduced && 'animate-fade-up',
          )}
        >
          <div className={cn('relative h-full w-full', !reduced && 'animate-float')}>
            <Image src="/images/auth-hero.png" alt="" fill priority className="object-contain" />
          </div>
        </div>

        <div className="mt-10 grid grid-cols-2 gap-6">
          {FEATURES.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <div
                key={feature.title}
                style={!reduced ? stagger(index, 80, 250) : undefined}
                className={cn(
                  'group flex flex-col items-start gap-2',
                  !reduced && 'animate-fade-up',
                )}
              >
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand/10 text-brand transition-transform duration-200 group-hover:scale-110">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <p className="text-sm font-semibold">{feature.title}</p>
                <p className="text-xs leading-relaxed text-muted-foreground">{feature.body}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
