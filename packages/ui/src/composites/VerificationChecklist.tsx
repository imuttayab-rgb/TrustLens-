/** Reusable UI rendering and interaction component: VerificationChecklist. */
import { VERIFICATION_LABELS, type VerificationStatus } from '@trustlens/constants';
import { Check, ChevronRight, Clock, X } from 'lucide-react';
import type { ElementType } from 'react';
import { cn } from '../lib/cn';

export interface ChecklistItem {
  key: string;
  label: string;
  status: VerificationStatus;
  pointsAvailable: number;
  actionUrl?: string | null;
}

const ICON: Record<string, typeof Check> = {
  VERIFIED: Check,
  PROCESSING: Clock,
  PENDING: Clock,
  REJECTED: X,
  FAILED: X,
  EXPIRED: X,
  NOT_STARTED: ChevronRight,
};

const TONE: Record<string, string> = {
  VERIFIED: 'text-risk-low bg-risk-low-bg',
  PROCESSING: 'text-risk-medium bg-risk-medium-bg',
  PENDING: 'text-risk-medium bg-risk-medium-bg',
  REJECTED: 'text-risk-high bg-risk-high-bg',
  FAILED: 'text-risk-high bg-risk-high-bg',
  EXPIRED: 'text-risk-high bg-risk-high-bg',
  NOT_STARTED: 'text-risk-unknown bg-risk-unknown-bg',
};

/**
 * Shows what each check is WORTH, not just whether it is done.
 *
 * That turns the score from a verdict into a path - which is the difference
 * between sellers cooperating with the system and resenting it.
 */
export function VerificationChecklist({
  items,
  className,
  actionLink,
}: {
  items: ChecklistItem[];
  className?: string;
  /** Router-aware link supplied by the host app; defaults to a plain anchor. */
  actionLink?: ElementType;
}) {
  const earned = items
    .filter((i) => i.status === 'VERIFIED')
    .reduce((sum, i) => sum + i.pointsAvailable, 0);
  const total = items.reduce((sum, i) => sum + i.pointsAvailable, 0);

  return (
    <div className={cn('space-y-3', className)}>
      <p className="text-muted-foreground text-sm">
        <span className="text-foreground font-semibold tabular-nums">{earned}</span> of {total}{' '}
        verification points earned
      </p>

      <ul className="space-y-2">
        {items.map((item) => {
          const Icon = ICON[item.status] ?? ChevronRight;
          const done = item.status === 'VERIFIED';
          const Wrapper = item.actionUrl && !done ? (actionLink ?? 'a') : 'div';

          return (
            <li key={item.key}>
              <Wrapper
                {...(item.actionUrl && !done ? { href: item.actionUrl } : {})}
                className={cn(
                  'border-border flex items-center gap-3 rounded-lg border p-3',
                  item.actionUrl &&
                    !done &&
                    'hover:bg-muted focus-visible:ring-ring transition-colors focus-visible:ring-2 focus-visible:outline-none',
                )}
              >
                <span className={cn('rounded-full p-1.5', TONE[item.status])} aria-hidden="true">
                  <Icon className="h-4 w-4" strokeWidth={2.5} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{item.label}</p>
                  <p className="text-muted-foreground text-sm">
                    {VERIFICATION_LABELS[item.status]}
                  </p>
                </div>
                <span
                  className={cn(
                    'shrink-0 text-sm font-semibold tabular-nums',
                    done ? 'text-risk-low' : 'text-muted-foreground',
                  )}
                >
                  {done ? '+' : ''}
                  {item.pointsAvailable}
                </span>
              </Wrapper>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
