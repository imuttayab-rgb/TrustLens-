'use client';

import { stagger, useInView, usePrefersReducedMotion } from '@/lib/motion';
import { cn } from '@trustlens/ui';
import { Activity, Fingerprint, Mail, MapPin, ScanFace, ScrollText } from 'lucide-react';

/**
 * The six checks, each carrying the points it is actually worth.
 *
 * The points are the structural device here, not decoration: they are the real
 * weights from the scoring model, so the grid doubles as an honest answer to
 * "how much does any one of these matter". A scammer has to defeat each one
 * separately, and this is where that claim becomes checkable.
 */
const CHECKS = [
  {
    icon: ScanFace,
    title: 'Identity',
    body: 'The CNIC is read, cross-checked against itself, and the selfie is compared with the photo on it.',
    points: 30,
  },
  {
    icon: Mail,
    title: 'Contact',
    body: 'Phone by one-time code, email by link. Throwaway numbers and disposable addresses score lower.',
    points: 25,
  },
  {
    icon: Fingerprint,
    title: 'Device',
    body: 'Flags one device quietly running several seller accounts — the cheapest way to rebuild after a ban.',
    points: 11,
  },
  {
    icon: MapPin,
    title: 'Network',
    body: 'VPN, proxy and location consistency. Using a VPN is not fraud, so it never sinks a score alone.',
    points: 10,
  },
  {
    icon: ScrollText,
    title: 'Listings',
    body: 'Reads the ad for pressure tactics, advance-payment demands and prices far below the going rate.',
    points: 15,
  },
  {
    icon: Activity,
    title: 'History',
    body: 'How long the account has existed and how steadily it has been used. A day-old account earns nothing here.',
    points: 9,
  },
] as const;

export function ChecksGrid() {
  const { ref, inView } = useInView<HTMLDivElement>();
  const reduced = usePrefersReducedMotion();

  return (
    <div ref={ref} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {CHECKS.map((check, index) => {
        const Icon = check.icon;
        return (
          <article
            key={check.title}
            style={inView && !reduced ? stagger(index, 70) : undefined}
            className={cn(
              'group relative overflow-hidden rounded-xl border border-border/70 bg-card/50 p-5',
              'transition-[transform,border-color,background-color] duration-300',
              'hover:-translate-y-1 hover:border-brand/35 hover:bg-card/80',
              inView && !reduced && 'animate-fade-up',
              !inView && !reduced && 'opacity-0',
            )}
          >
            {/* Light wakes under the cursor. Contained to the card so it reads
                as the card responding, not as a page-wide effect. */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 bg-gradient-to-br from-brand/10 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
            />

            <div className="relative">
              <div className="flex items-start justify-between gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-lg border border-border/70 bg-background/60 transition-colors duration-300 group-hover:border-brand/40">
                  <Icon
                    className="h-4.5 w-4.5 text-muted-foreground transition-colors duration-300 group-hover:text-brand"
                    aria-hidden="true"
                  />
                </span>
                <span className="text-right text-xs text-muted-foreground">
                  <span className="block text-lg font-bold tabular-nums leading-none text-foreground">
                    {check.points}
                  </span>
                  points
                </span>
              </div>

              <h3 className="mt-4 text-base font-semibold">{check.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{check.body}</p>
            </div>
          </article>
        );
      })}
    </div>
  );
}
