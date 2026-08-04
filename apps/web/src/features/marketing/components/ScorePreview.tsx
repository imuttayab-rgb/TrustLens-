'use client';

import { stagger, useCountUp, useInView, usePrefersReducedMotion } from '@/lib/motion';
import { cn } from '@trustlens/ui';
import {
  Activity,
  BadgeCheck,
  Check,
  Fingerprint,
  Lock,
  Mail,
  MapPin,
  Phone,
  ScanFace,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';

/**
 * The signature element.
 *
 * Everything else on the page describes the product; this *is* the product -
 * a score and, beside it, the exact reasons for that score. The two halves are
 * deliberately equal in visual weight, because a number without its reasons is
 * the thing TrustLens exists to replace.
 *
 * The figures are a worked example, not live data, and the card says so.
 */

const SCORE = 86;

const SIGNALS = [
  {
    icon: ScanFace,
    label: 'Identity verified',
    detail: 'CNIC read and face matched',
    state: 'pass',
  },
  { icon: Phone, label: 'Phone verified', detail: 'One-time code confirmed', state: 'pass' },
  { icon: Mail, label: 'Email verified', detail: 'Address is real and active', state: 'pass' },
  {
    icon: Fingerprint,
    label: 'Device checked',
    detail: 'Not shared with other accounts',
    state: 'pass',
  },
  { icon: MapPin, label: 'Location', detail: 'Connecting through a VPN', state: 'warn' },
  { icon: Activity, label: 'Listings analysed', detail: 'No scam patterns found', state: 'pass' },
  { icon: BadgeCheck, label: 'Account age', detail: 'Selling since January 2024', state: 'pass' },
] as const;

export function ScorePreview({ className }: { className?: string }) {
  const { ref, inView } = useInView<HTMLDivElement>('-20% 0px');
  const reduced = usePrefersReducedMotion();
  const value = useCountUp(SCORE, inView);

  const RADIUS = 78;
  const CIRCUMFERENCE = Math.PI * RADIUS; // semicircle
  const shown = Math.round(value);
  const offset = CIRCUMFERENCE * (1 - (reduced ? SCORE : value) / 100);

  return (
    <div
      ref={ref}
      className={cn(
        'relative rounded-2xl border border-border/80 bg-card/70 p-4 backdrop-blur-xl sm:p-5',
        // A single soft ring rather than a heavy drop shadow: on a near-black
        // surface a shadow is invisible, and a ring reads as emitted light.
        'shadow-[0_0_0_1px_hsl(var(--brand)/0.08),0_24px_70px_-30px_hsl(var(--brand)/0.35)]',
        className,
      )}
    >
      <div className="flex items-center gap-2 px-1 pb-4">
        <ShieldCheck className="h-4 w-4 text-brand" aria-hidden="true" />
        <span className="text-sm font-semibold">Trust Score</span>
        <span className="ml-auto text-xs text-muted-foreground">Worked example</span>
      </div>

      <div className="grid gap-3 sm:grid-cols-[minmax(0,0.85fr)_minmax(0,1fr)]">
        {/* ── Gauge ── */}
        <div className="relative overflow-hidden rounded-xl border border-border/70 bg-background/40 p-4">
          <div className="relative mx-auto w-full max-w-[190px]">
            <svg
              viewBox="0 0 200 116"
              className="w-full"
              role="img"
              aria-label={`Trust Score ${SCORE} out of 100, low risk`}
            >
              <path
                d="M 22 104 A 78 78 0 0 1 178 104"
                fill="none"
                stroke="hsl(var(--muted))"
                strokeWidth="13"
                strokeLinecap="round"
              />
              <path
                d="M 22 104 A 78 78 0 0 1 178 104"
                fill="none"
                stroke="hsl(var(--risk-low))"
                strokeWidth="13"
                strokeLinecap="round"
                strokeDasharray={CIRCUMFERENCE}
                strokeDashoffset={offset}
                style={{ transition: reduced ? 'none' : 'stroke-dashoffset 80ms linear' }}
              />
            </svg>

            <div className="absolute inset-x-0 bottom-1 text-center">
              <div className="text-5xl font-extrabold tabular-nums tracking-tight text-risk-low">
                {shown}
              </div>
              <div className="text-xs text-muted-foreground">out of 100</div>
            </div>
          </div>

          <div className="mt-3 flex items-center justify-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-risk-low" aria-hidden="true" />
            <span className="text-xs font-semibold uppercase tracking-wide text-risk-low">
              Low risk
            </span>
          </div>
          <p className="mt-1 text-center text-xs text-muted-foreground">
            Six of seven checks passed
          </p>

          {/* One-shot sheen as the arc settles. Purely atmospheric. */}
          {!reduced && inView && (
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 animate-sheen bg-gradient-to-r from-transparent via-white/[0.06] to-transparent"
            />
          )}
        </div>

        {/* ── Reasons ── */}
        <div className="rounded-xl border border-border/70 bg-background/40 p-3">
          <p className="px-1 pb-2 text-xs font-semibold">Why this score?</p>
          <ul className="space-y-0.5">
            {SIGNALS.map((signal, index) => {
              const Icon = signal.icon;
              const warn = signal.state === 'warn';
              return (
                <li
                  key={signal.label}
                  style={inView && !reduced ? stagger(index, 65, 260) : undefined}
                  className={cn(
                    'group flex items-center gap-2.5 rounded-lg px-1.5 py-1.5 transition-colors',
                    'hover:bg-muted/60',
                    inView && !reduced && 'animate-fade-up',
                    !inView && !reduced && 'opacity-0',
                  )}
                >
                  <Icon
                    className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-foreground"
                    aria-hidden="true"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-xs font-medium">{signal.label}</span>
                    <span className="block truncate text-[11px] text-muted-foreground">
                      {signal.detail}
                    </span>
                  </span>
                  <span
                    className={cn(
                      'grid h-4 w-4 shrink-0 place-items-center rounded-full',
                      warn ? 'bg-risk-medium/15 text-risk-medium' : 'bg-risk-low/15 text-risk-low',
                      inView && !reduced && 'animate-pop-in',
                    )}
                    style={inView && !reduced ? stagger(index, 65, 380) : undefined}
                  >
                    {warn ? (
                      <TriangleAlert className="h-2.5 w-2.5" aria-hidden="true" />
                    ) : (
                      <Check className="h-2.5 w-2.5" strokeWidth={3} aria-hidden="true" />
                    )}
                    <span className="sr-only">{warn ? 'Needs attention' : 'Passed'}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2 px-1 text-[11px] text-muted-foreground">
        <Lock className="h-3 w-3" aria-hidden="true" />
        <span>Checks run on encrypted data. Documents are deleted after a decision.</span>
      </div>
    </div>
  );
}
