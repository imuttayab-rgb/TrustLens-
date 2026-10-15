/** Reusable UI rendering and interaction component: WhyChooseUs. */
'use client';

import { stagger, useInView, usePrefersReducedMotion } from '@/lib/motion';
import { cn } from '@trustlens/utils';
import { MapPin, MessageCircle, ScanFace, ShieldCheck } from 'lucide-react';
import { useTranslations } from 'next-intl';

const FEATURES = [
  { icon: ScanFace, key: 'liveIdentity' },
  { icon: ShieldCheck, key: 'explainableScore' },
  { icon: MessageCircle, key: 'safeChat' },
  { icon: MapPin, key: 'safeMeet' },
] as const;

export function WhyChooseUs() {
  const t = useTranslations('Home');
  const { ref, inView } = useInView<HTMLDivElement>();
  const reduced = usePrefersReducedMotion();

  return (
    <section className="border-y border-border/70 bg-muted/30">
      <div className="mx-auto max-w-7xl px-5 py-10 sm:px-8">
        <div ref={ref} className="grid gap-8 lg:grid-cols-[1fr_2fr] lg:items-center">
          <h2 className="text-xl font-bold tracking-tight sm:text-2xl">{t('whyChoose')}</h2>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <div
                  key={feature.key}
                  style={inView && !reduced ? stagger(index, 80) : undefined}
                  className={cn(
                    'group flex items-start gap-3 rounded-lg p-2 transition-colors duration-200 hover:bg-card',
                    !reduced && inView && 'animate-fade-up',
                    !reduced && !inView && 'opacity-0',
                  )}
                >
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand transition-transform duration-200 group-hover:scale-110">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold">{t(`features.${feature.key}.title`)}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                      {t(`features.${feature.key}.body`)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
