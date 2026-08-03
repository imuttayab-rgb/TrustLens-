'use client';

import { Alert, Progress, Spinner, cn } from '@trustlens/ui';
import type { ListingAnalysis } from '../hooks/use-listings';

/** Plain-English names for the scam patterns the analysers report. */
const LABEL_TEXT: Record<string, string> = {
  urgency_pressure: 'Pressures the buyer to decide immediately',
  advance_fee: 'Asks for payment before the buyer sees the item',
  off_platform: 'Pushes the conversation somewhere unmonitored',
  too_good_to_be_true: 'Priced far below what the item is worth',
  stolen_photo: 'Images appear elsewhere online',
  contact_only: 'Gives no way to verify the item before paying',
  vague_description: 'Avoids specifics a genuine seller would give',
};

function tone(risk: number): 'success' | 'warning' | 'error' {
  if (risk >= 60) return 'error';
  if (risk >= 30) return 'warning';
  return 'success';
}

export function ListingRiskPanel({
  analysis,
  status,
  className,
}: {
  analysis: ListingAnalysis | null;
  status: string;
  className?: string;
}) {
  if (status === 'ANALYSING' || !analysis) {
    return (
      <div className={cn('flex items-center gap-3 text-sm', className)}>
        <Spinner label="Analysing this listing" />
        <span className="text-muted-foreground">Checking this listing for scam patterns…</span>
      </div>
    );
  }

  const risk = analysis.riskScore;
  const deviation = analysis.priceDeviationPct;

  return (
    <div className={cn('space-y-3', className)}>
      <div>
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-sm font-medium">Listing risk</span>
          <span className="text-sm font-semibold tabular-nums">{Math.round(risk)}/100</span>
        </div>
        <Progress value={risk} label="Listing risk score" className="mt-1.5" />
      </div>

      {analysis.labels.length > 0 ? (
        <Alert tone={tone(risk)} title="What the analysis found">
          <ul className="mt-1 list-inside list-disc space-y-0.5">
            {analysis.labels.map((label) => (
              <li key={label.code}>{LABEL_TEXT[label.code] ?? label.code.replace(/_/g, ' ')}</li>
            ))}
          </ul>
        </Alert>
      ) : (
        <Alert tone="success">No scam patterns were found in this listing.</Alert>
      )}

      {/* Only underpricing is reported. An overpriced listing is a bad deal,
          not a scam, and flagging it would train sellers to ignore this. */}
      {deviation !== null && deviation <= -35 && (
        <Alert
          tone={deviation <= -60 ? 'error' : 'warning'}
          title="Price looks too good to be true"
        >
          This is {Math.abs(Math.round(deviation))}% below the typical price for its category.
        </Alert>
      )}

      <p className="text-xs text-muted-foreground">
        Assessed by {analysis.analyzerType.toLowerCase()} · confidence{' '}
        {Math.round(analysis.confidence * 100)}%
      </p>
    </div>
  );
}
