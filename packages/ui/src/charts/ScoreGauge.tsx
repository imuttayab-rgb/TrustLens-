'use client';

/**
 * The Trust Score gauge - the single most important component in the product.
 *
 * Three deliberate accessibility decisions:
 *
 * 1. Colour is NEVER the only carrier of meaning. The band label ("Low risk")
 *    is always rendered alongside the arc. A colour-blind buyer misreading
 *    amber as green is a person about to be defrauded.
 * 2. `UNKNOWN` renders slate, never green or red. A brand-new honest seller
 *    and a proven scammer must not look the same, and neither should be given
 *    a colour that implies a verdict we have not reached.
 * 3. The SVG carries `role="img"` and a full `aria-label`, so a screen reader
 *    announces the score and the band rather than "graphic".
 */
import { RISK_PRESENTATION, type RiskLevel } from '@trustlens/constants';
import { cn } from '../lib/cn';

export interface ScoreGaugeProps {
  score: number;
  riskLevel: RiskLevel;
  /** Rendered under the band label, e.g. "based on 12 of 14 checks". */
  caption?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZES = {
  sm: { box: 120, stroke: 10, score: 'text-2xl', label: 'text-xs' },
  md: { box: 180, stroke: 14, score: 'text-4xl', label: 'text-sm' },
  lg: { box: 240, stroke: 18, score: 'text-6xl', label: 'text-base' },
} as const;

const ARC_COLOR: Record<RiskLevel, string> = {
  LOW: 'stroke-risk-low',
  MEDIUM: 'stroke-risk-medium',
  HIGH: 'stroke-risk-high',
  UNKNOWN: 'stroke-risk-unknown',
};

const TEXT_COLOR: Record<RiskLevel, string> = {
  LOW: 'text-risk-low',
  MEDIUM: 'text-risk-medium',
  HIGH: 'text-risk-high',
  UNKNOWN: 'text-risk-unknown',
};

export function ScoreGauge({
  score,
  riskLevel,
  caption,
  size = 'md',
  className,
}: ScoreGaugeProps) {
  const { box, stroke, score: scoreText, label: labelText } = SIZES[size];
  const radius = (box - stroke) / 2;
  const centre = box / 2;

  // A 270-degree arc: it reads as a gauge rather than a pie, and leaves room
  // at the bottom for the band label.
  const sweep = 270;
  const circumference = 2 * Math.PI * radius;
  const arcLength = (sweep / 360) * circumference;
  const filled = riskLevel === 'UNKNOWN' ? 0 : (score / 100) * arcLength;

  const presentation = RISK_PRESENTATION[riskLevel];
  const displayScore = riskLevel === 'UNKNOWN' ? '?' : String(score);

  return (
    <div className={cn('inline-flex flex-col items-center gap-2', className)}>
      <div className="relative" style={{ width: box, height: box }}>
        <svg
          width={box}
          height={box}
          viewBox={`0 0 ${box} ${box}`}
          role="img"
          aria-label={`Trust score ${displayScore} out of 100. ${presentation.label}.`}
          className="-rotate-[135deg]"
        >
          <circle
            cx={centre}
            cy={centre}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${arcLength} ${circumference}`}
            className="stroke-muted"
          />
          <circle
            cx={centre}
            cy={centre}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference}`}
            className={cn(ARC_COLOR[riskLevel], 'transition-[stroke-dasharray] duration-700')}
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn('font-bold tabular-nums leading-none', scoreText, TEXT_COLOR[riskLevel])}>
            {displayScore}
          </span>
          {riskLevel !== 'UNKNOWN' && (
            <span className="text-muted-foreground mt-1 text-xs">out of 100</span>
          )}
        </div>
      </div>

      {/* The label is not decoration - it is what makes the gauge readable
          without relying on colour. */}
      <div className="text-center">
        <p className={cn('font-semibold', labelText, TEXT_COLOR[riskLevel])}>
          {presentation.label}
        </p>
        {caption && <p className="text-muted-foreground mt-0.5 text-xs">{caption}</p>}
      </div>
    </div>
  );
}
