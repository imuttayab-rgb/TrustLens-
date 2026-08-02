'use client';

import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';
import * as React from 'react';
import { cn } from '../lib/cn';

export type AlertTone = 'info' | 'success' | 'warning' | 'error';

const TONE: Record<AlertTone, { box: string; icon: typeof Info }> = {
  info: { box: 'bg-muted text-foreground', icon: Info },
  success: { box: 'bg-risk-low-bg text-risk-low', icon: CheckCircle2 },
  warning: { box: 'bg-risk-medium-bg text-risk-medium', icon: AlertTriangle },
  error: { box: 'bg-risk-high-bg text-risk-high', icon: XCircle },
};

export interface AlertProps {
  tone?: AlertTone | undefined;
  title?: string | undefined;
  children?: React.ReactNode | undefined;
  /**
   * Surfaced in small print so a user can quote it. Turns "it didn't work"
   * into a single log query. `| undefined` because callers pass it straight
   * from ApiError under exactOptionalPropertyTypes.
   */
  requestId?: string | undefined;
  className?: string | undefined;
}

export function Alert({ tone = 'info', title, children, requestId, className }: AlertProps) {
  const { box, icon: Icon } = TONE[tone];
  return (
    <div
      // Errors interrupt; everything else waits for a pause in speech.
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn('flex gap-3 rounded-md p-3 text-sm', box, className)}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn(title && 'mt-0.5')}>{children}</div>}
        {requestId && <p className="mt-1 font-mono text-xs opacity-80">Reference: {requestId}</p>}
      </div>
    </div>
  );
}
