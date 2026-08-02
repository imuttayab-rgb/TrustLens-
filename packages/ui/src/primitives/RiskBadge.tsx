import { RISK_PRESENTATION, type RiskLevel } from '@trustlens/constants';
import { AlertTriangle, HelpCircle, ShieldAlert, ShieldCheck } from 'lucide-react';
import { cn } from '../lib/cn';

const STYLES: Record<RiskLevel, string> = {
  LOW: 'bg-risk-low-bg text-risk-low',
  MEDIUM: 'bg-risk-medium-bg text-risk-medium',
  HIGH: 'bg-risk-high-bg text-risk-high',
  UNKNOWN: 'bg-risk-unknown-bg text-risk-unknown',
};

const ICONS: Record<RiskLevel, typeof ShieldCheck> = {
  LOW: ShieldCheck,
  MEDIUM: AlertTriangle,
  HIGH: ShieldAlert,
  UNKNOWN: HelpCircle,
};

/**
 * Always renders icon + text, never colour alone (WCAG 1.4.1). This is the
 * component a buyer glances at before deciding whether to pay, so it has to be
 * unambiguous to everyone.
 */
export function RiskBadge({
  riskLevel,
  score,
  className,
}: {
  riskLevel: RiskLevel;
  score?: number | undefined;
  className?: string | undefined;
}) {
  const Icon = ICONS[riskLevel];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold',
        STYLES[riskLevel],
        className,
      )}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      {RISK_PRESENTATION[riskLevel].label}
      {score != null && riskLevel !== 'UNKNOWN' && (
        <span className="tabular-nums opacity-80">· {score}</span>
      )}
    </span>
  );
}
