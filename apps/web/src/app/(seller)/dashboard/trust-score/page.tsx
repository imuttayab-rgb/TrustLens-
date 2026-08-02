import { serverFetch } from '@/lib/api/server';
import type { RiskLevel, SignalCategory, SignalStatus } from '@trustlens/constants';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ScoreGauge,
  SignalBreakdown,
} from '@trustlens/ui';
import { formatDateTime } from '@trustlens/utils';
import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

export const metadata: Metadata = { title: 'Your Trust Score' };
export const dynamic = 'force-dynamic';

interface ScoreDetail {
  sellerId: string;
  score: number;
  riskLevel: RiskLevel;
  confidence: number;
  modelVersion: string;
  computedAt: string;
  capApplied: number | null;
  summary: string;
  signals: {
    code: string;
    category: SignalCategory;
    status: SignalStatus;
    pointsAwarded: number;
    pointsPossible: number;
    confidence: number;
    reasonCode: string;
    reasonText: string;
  }[];
}

interface Improvement {
  signalCode: string;
  pointsAvailable: number;
  action: string;
}

export default async function TrustScorePage() {
  const seller = await serverFetch<{ id: string }>('/api/v1/sellers/me');
  if (!seller) redirect('/login?next=/dashboard/trust-score');

  const score = await serverFetch<ScoreDetail>(`/api/v1/sellers/${seller.id}/trust-score`);
  const improvements =
    (await serverFetch<Improvement[]>(`/api/v1/sellers/${seller.id}/trust-score/improvements`)) ??
    [];

  if (!score) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="text-2xl font-bold">Your Trust Score</h1>
        <p className="mt-4 text-muted-foreground">
          Your score has not been calculated yet. Complete a verification check to get started.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <header className="flex flex-col items-center gap-3 text-center">
        <ScoreGauge score={score.score} riskLevel={score.riskLevel} size="lg" />
        <p className="max-w-prose">{score.summary}</p>
        <p className="text-sm text-muted-foreground">
          Calculated {formatDateTime(score.computedAt)} using model {score.modelVersion}
        </p>
      </header>

      {/* A capped score is not an arithmetic result, and saying so plainly is
          the difference between a seller understanding it and appealing it. */}
      {score.capApplied != null && (
        <div className="mt-8 rounded-lg bg-risk-high-bg p-4 text-sm text-risk-high">
          <p className="font-semibold">This score was capped at {score.capApplied}.</p>
          <p className="mt-1">
            A critical check failed, so the score is limited regardless of how the other checks
            scored. Fixing that check is the only way to raise it.
          </p>
        </div>
      )}

      {improvements.length > 0 && (
        <Card className="mt-8">
          <CardHeader>
            <CardTitle>How to raise your score</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-3">
              {improvements.map((item) => (
                <li key={item.signalCode} className="flex items-start gap-3">
                  <span className="shrink-0 text-sm font-semibold tabular-nums text-risk-low">
                    +{item.pointsAvailable.toFixed(0)}
                  </span>
                  <span className="text-sm">{item.action}</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Full breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <SignalBreakdown signals={score.signals} />
        </CardContent>
      </Card>
    </main>
  );
}
