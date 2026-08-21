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
import { type RiskLevel, SIGNAL_CATEGORIES, type SignalCategory } from '@trustlens/constants';
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
  reasons: { code: string; impact: string; category: string; text: string }[];
  modelVersion: string;
  computedAt: string;
  expiresAt: string;
  unavailableSignals: string[];
}

/**
 * Reads the first-party buyer route, not the partner API at `/public/v1`.
 *
 * The partner API requires an API key, and this page holds none - which is
 * why it rendered not-found for every seller until P0-12. It could have been
 * issued one, but the buyer page is not a partner: sharing that credential
 * path would mean a revoked key or an exhausted quota takes down the most
 * visible screen in the product. Same PII-free payload, different door.
 */
async function getScore(handle: string): Promise<PublicScore | null> {
  return serverFetch<PublicScore>(
    `/api/v1/public/sellers/${encodeURIComponent(handle)}/trust-score`,
  );
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
  const signals: SignalRow[] = score.reasons.map((reason) => ({
    code: reason.code,
    // Sent by the API. It used to be hardcoded to 'IDENTITY', which labelled
    // every row "Identity" - a confirmed email address was presented to
    // buyers as an identity check. Invisible until P0-12, because the page
    // 404'd before it could render a single reason.
    category: SIGNAL_CATEGORIES.includes(reason.category as SignalCategory)
      ? (reason.category as SignalCategory)
      : 'IDENTITY',
    status: reason.impact === 'NEGATIVE' ? 'FAIL' : 'PASS',
    pointsAwarded: reason.impact === 'NEGATIVE' ? 0 : 1,
    pointsPossible: 1,
    confidence: score.confidence,
    reasonCode: reason.code,
    reasonText: reason.text,
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
        <p className="text-sm text-muted-foreground">
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
              <div key={key} className="rounded-lg border border-border p-3">
                <dt className="text-sm capitalize text-muted-foreground">{key}</dt>
                <dd className="mt-0.5 font-medium">{value.replace(/_/g, ' ').toLowerCase()}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      <section className="mt-10 text-sm text-muted-foreground">
        <p>
          A Trust Score is an assessment based on the checks listed above, not a guarantee. Always
          meet in a public place, inspect goods before paying, and never send money in advance to
          someone you have not met.
        </p>
      </section>
    </main>
  );
}
