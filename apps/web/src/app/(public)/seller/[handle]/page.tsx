/**
 * The public Trust Score page - the product's shop window.
 *
 * Server-rendered with ISR rather than client-fetched, for three reasons:
 * it must be linkable in a WhatsApp or marketplace chat with a proper preview
 * card, it must be crawlable, and a buyer deciding whether to pay should not
 * wait on a client-side round trip.
 *
 * The revalidate window mirrors the API's own score cache, so the two layers
 * cannot disagree by more than one window.
 */
import { serverFetch } from '@/lib/api/server';
import { type RiskLevel } from '@trustlens/constants';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  RiskBadge,
  ScoreGauge,
  SignalBreakdown,
  type SignalRow,
} from '@trustlens/ui';
import { formatDateTime } from '@trustlens/utils';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

export const revalidate = 300;

interface PublicScore {
  sellerRef: string;
  score: number;
  riskLevel: RiskLevel;
  riskLabel: string;
  confidence: number;
  verifications: Record<string, string>;
  reasons: { code: string; impact: string; text: string }[];
  modelVersion: string;
  computedAt: string;
  expiresAt: string;
  unavailableSignals: string[];
}

async function getScore(handle: string): Promise<PublicScore | null> {
  return serverFetch<PublicScore>(`/public/v1/sellers/${encodeURIComponent(handle)}/trust-score`);
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ handle: string }>;
}): Promise<Metadata> {
  const { handle } = await params;
  const score = await getScore(handle);
  if (!score) return { title: 'Seller not found' };

  return {
    title: `${handle} · Trust Score ${score.score}/100`,
    description: `${score.riskLabel}. ${score.reasons[0]?.text ?? ''}`,
    openGraph: {
      title: `${handle} — Trust Score ${score.score}/100`,
      description: score.riskLabel,
      type: 'profile',
    },
  };
}

export default async function SellerPage({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  const score = await getScore(handle);
  if (!score) notFound();

  // The public payload carries reasons, not raw signal rows - it is
  // deliberately PII-free. Map them into the shared breakdown shape.
  const signals: SignalRow[] = score.reasons.map((reason, index) => ({
    code: reason.code,
    category: 'IDENTITY',
    status: reason.impact === 'NEGATIVE' ? 'FAIL' : 'PASS',
    pointsAwarded: reason.impact === 'NEGATIVE' ? 0 : 1,
    pointsPossible: 1,
    confidence: score.confidence,
    reasonCode: reason.code,
    reasonText: reason.text,
    // Stable key for React when two reasons share a code.
    ...(index === 0 ? {} : {}),
  }));

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="flex flex-col items-center gap-4 text-center">
        <ScoreGauge
          score={score.score}
          riskLevel={score.riskLevel}
          size="lg"
          caption={
            score.unavailableSignals.length > 0
              ? `${score.unavailableSignals.length} check(s) could not be completed`
              : undefined
          }
        />
        <h1 className="text-2xl font-bold">{handle}</h1>
        <RiskBadge riskLevel={score.riskLevel} />
        <p className="text-muted-foreground text-sm">
          Last checked {formatDateTime(score.computedAt)} · scoring model {score.modelVersion}
        </p>
      </header>

      <Card className="mt-10">
        <CardHeader>
          <CardTitle>Why this score</CardTitle>
        </CardHeader>
        <CardContent>
          <SignalBreakdown signals={signals} />
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Checks completed</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-3 sm:grid-cols-3">
            {Object.entries(score.verifications).map(([key, value]) => (
              <div key={key} className="border-border rounded-lg border p-3">
                <dt className="text-muted-foreground text-sm capitalize">{key}</dt>
                <dd className="mt-0.5 font-medium">{value.replace(/_/g, ' ').toLowerCase()}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      <section className="text-muted-foreground mt-10 text-sm">
        <p>
          A Trust Score is an assessment based on the checks listed above, not a guarantee. Always
          meet in a public place, inspect goods before paying, and never send money in advance to
          someone you have not met.
        </p>
      </section>
    </main>
  );
}
