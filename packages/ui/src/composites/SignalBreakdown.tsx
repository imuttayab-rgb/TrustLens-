'use client';

/**
 * The per-signal breakdown - this component IS the explainability feature.
 *
 * Everything rendered here comes straight from `trust_score_signals`, frozen
 * at computation time. Nothing is recalculated in the browser, so what a
 * seller sees in an appeal is exactly what the engine decided.
 *
 * Ordering matters: losses first, largest first. "Why am I not higher" is the
 * question sellers actually ask.
 */
import { CATEGORY_LABELS, type SignalCategory, type SignalStatus } from '@trustlens/constants';
import { AlertTriangle, Check, HelpCircle, Minus, X } from 'lucide-react';
import { cn } from '../lib/cn';

export interface SignalRow {
  code: string;
  category: SignalCategory;
  status: SignalStatus;
  pointsAwarded: number;
  pointsPossible: number;
  confidence: number;
  reasonCode: string;
  reasonText: string;
}

export interface SignalBreakdownProps {
  signals: SignalRow[];
  className?: string;
}

/**
 * Icon + colour + text for each status. Note every status has an icon AND a
 * distinct label, so meaning survives without colour perception.
 */
const STATUS_PRESENTATION: Record<
  SignalStatus,
  { icon: typeof Check; label: string; className: string }
> = {
  PASS: { icon: Check, label: 'Passed', className: 'text-risk-low bg-risk-low-bg' },
  PARTIAL: {
    icon: AlertTriangle,
    label: 'Partly passed',
    className: 'text-risk-medium bg-risk-medium-bg',
  },
  FAIL: { icon: X, label: 'Failed', className: 'text-risk-high bg-risk-high-bg' },
  UNAVAILABLE: {
    icon: HelpCircle,
    // Wording matters: this is OUR outage, not the seller's failure, and the
    // score excludes it entirely rather than counting it as zero.
    label: 'Could not be checked',
    className: 'text-risk-unknown bg-risk-unknown-bg',
  },
  NOT_APPLICABLE: {
    icon: Minus,
    label: 'Not applicable',
    className: 'text-risk-unknown bg-risk-unknown-bg',
  },
};

function pointsLost(signal: SignalRow): number {
  return signal.pointsPossible - signal.pointsAwarded;
}

export function SignalBreakdown({ signals, className }: SignalBreakdownProps) {
  const counted = signals.filter(
    (s) => s.status !== 'UNAVAILABLE' && s.status !== 'NOT_APPLICABLE',
  );
  const excluded = signals.filter(
    (s) => s.status === 'UNAVAILABLE' || s.status === 'NOT_APPLICABLE',
  );

  // Losses first (biggest first), then confirmations.
  const ordered = [...counted].sort((a, b) => {
    const delta = pointsLost(b) - pointsLost(a);
    return delta !== 0 ? delta : b.pointsAwarded - a.pointsAwarded;
  });

  return (
    <div className={cn('space-y-6', className)}>
      <ul className="divide-border divide-y">
        {ordered.map((signal) => (
          <SignalItem key={signal.code} signal={signal} />
        ))}
      </ul>

      {excluded.length > 0 && (
        <section
          aria-labelledby="excluded-heading"
          className="border-border bg-muted/40 rounded-lg border p-4"
        >
          <h3 id="excluded-heading" className="text-sm font-semibold">
            Not included in this score
          </h3>
          <p className="text-muted-foreground mt-1 text-sm">
            These checks could not be completed, so they were left out of the calculation rather
            than counted as failures.
          </p>
          <ul className="mt-3 space-y-1">
            {excluded.map((signal) => (
              <li key={signal.code} className="text-muted-foreground text-sm">
                <span className="font-medium">{CATEGORY_LABELS[signal.category]}</span>
                {' — '}
                {signal.reasonText}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function SignalItem({ signal }: { signal: SignalRow }) {
  const presentation = STATUS_PRESENTATION[signal.status];
  const Icon = presentation.icon;
  const lost = pointsLost(signal);

  return (
    <li className="flex items-start gap-3 py-4">
      <span className={cn('mt-0.5 rounded-full p-1.5', presentation.className)} aria-hidden="true">
        <Icon className="h-4 w-4" strokeWidth={2.5} />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <p className="font-medium">{CATEGORY_LABELS[signal.category]}</p>
          <p className="text-muted-foreground text-sm tabular-nums">
            <span className="sr-only">{presentation.label}. Scored </span>
            {signal.pointsAwarded.toFixed(0)} / {signal.pointsPossible.toFixed(0)} points
          </p>
        </div>

        <p className="text-muted-foreground mt-1 text-sm">{signal.reasonText}</p>

        {lost > 0 && (
          <p className="text-risk-medium mt-1 text-xs font-medium">
            {lost.toFixed(0)} {lost === 1 ? 'point' : 'points'} available here
          </p>
        )}
      </div>
    </li>
  );
}
