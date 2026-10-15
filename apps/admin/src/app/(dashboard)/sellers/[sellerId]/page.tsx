/** Next.js route/layout composition for (dashboard)/sellers/[sellerId]: page. */
'use client';

import { useSellerDetail, useSellerTrustScore } from '@/features/sellers';
import { IdentityEvidence, useIdentityReview } from '@/features/review';
import {
  Alert,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  SignalBreakdown,
  Spinner,
} from '@trustlens/ui';
import Link from 'next/link';
import { useParams } from 'next/navigation';

const statusLabel = (value: string) => value.replaceAll('_', ' ');

export default function SellerDetailPage() {
  const params = useParams<{ sellerId: string }>();
  const { data: seller, error, isPending } = useSellerDetail(params.sellerId);
  const trustScore = useSellerTrustScore(params.sellerId);
  const identity = useIdentityReview(params.sellerId);

  if (isPending) {
    return (
      <div className="flex justify-center p-12">
        <Spinner label="Loading seller details" />
      </div>
    );
  }
  if (error || !seller) {
    return (
      <main className="p-8">
        <Alert tone="error">Unable to load this seller.</Alert>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6 sm:p-8">
      <Link href="/sellers" className="text-sm text-primary hover:underline">
        Back to sellers
      </Link>
      <header>
        <p className="text-sm text-muted-foreground">@{seller.handle}</p>
        <h1 className="text-2xl font-bold">{seller.displayName}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {seller.email}
          {seller.city ? ` · ${seller.city}` : ''}
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <p className="text-3xl font-bold">{seller.score ?? '—'}</p>
            <p className="text-sm text-muted-foreground">Current score</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-3xl font-bold">{seller.riskLevel ?? 'UNKNOWN'}</p>
            <p className="text-sm text-muted-foreground">Risk level</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p
              className={
                seller.isFlagged ? 'text-3xl font-bold text-risk-high' : 'text-3xl font-bold'
              }
            >
              {seller.isFlagged ? 'Yes' : 'No'}
            </p>
            <p className="text-sm text-muted-foreground">Flagged</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Verification status</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm sm:grid-cols-3">
          <div>
            <p className="text-muted-foreground">Identity</p>
            <p className="font-medium">{statusLabel(seller.identityStatus)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Phone</p>
            <p className="font-medium">{statusLabel(seller.phoneStatus)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Email</p>
            <p className="font-medium">{statusLabel(seller.emailStatus)}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Signal breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          {trustScore.isPending ? (
            <Spinner label="Loading the signal breakdown" />
          ) : trustScore.error ? (
            <Alert tone="error">The signal breakdown could not be loaded.</Alert>
          ) : !trustScore.data ? (
            <Alert tone="info">
              This seller has not been scored yet — no verification checks have completed.
            </Alert>
          ) : (
            <>
              {trustScore.data.capApplied != null && (
                <div className="mb-4 rounded-lg bg-risk-high-bg p-4 text-sm text-risk-high">
                  <p className="font-semibold">
                    This score is capped at {trustScore.data.capApplied}.
                  </p>
                  <p className="mt-1">
                    A critical check failed, capping the score regardless of the rest.
                  </p>
                </div>
              )}
              <SignalBreakdown signals={trustScore.data.signals} />
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Identity evidence</CardTitle>
        </CardHeader>
        <CardContent>
          <IdentityEvidence identity={identity} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Score history</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="w-full min-w-[620px] text-left text-sm">
            <thead className="border-b border-border/70 bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Trigger</th>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3">Computed</th>
              </tr>
            </thead>
            <tbody>
              {seller.scoreHistory.map((item) => (
                <tr key={item.id} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-3 font-semibold">{item.score}</td>
                  <td className="px-4 py-3">{item.riskLevel}</td>
                  <td className="px-4 py-3">
                    {statusLabel(item.trigger)}
                    {item.manualOverride ? ' · manual' : ''}
                  </td>
                  <td className="px-4 py-3">{item.modelVersion}</td>
                  <td className="px-4 py-3">{new Date(item.computedAt).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </main>
  );
}
