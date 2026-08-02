'use client';

import { Loader2 } from 'lucide-react';
import { cn } from '../lib/cn';

/**
 * Indeterminate progress.
 *
 * `label` is visually hidden but announced, so a screen reader user learns
 * *what* is loading rather than only that something is.
 */
export function Spinner({
  className,
  label = 'Loading',
}: {
  className?: string | undefined;
  label?: string | undefined;
}) {
  return (
    <span role="status" className="inline-flex items-center gap-2">
      <Loader2 className={cn('h-4 w-4 animate-spin', className)} aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </span>
  );
}

/** Determinate progress, 0-100. */
export function Progress({
  value,
  label,
  className,
}: {
  value: number;
  label?: string | undefined;
  className?: string | undefined;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className={cn('bg-muted h-2 w-full overflow-hidden rounded-full', className)}
    >
      <div
        className="bg-primary h-full transition-[width] duration-300 ease-out"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
