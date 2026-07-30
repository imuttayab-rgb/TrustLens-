import { serverFetch } from '@/lib/api/server';
import { type RiskLevel, type VerificationStatus } from '@trustlens/constants';
import {
  Card, CardContent, CardHeader, CardTitle, RiskBadge, ScoreGauge, VerificationChecklist,
} from '@trustlens/ui';
import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

export const metadata: Metadata = { title: 'Dashboard' };
export const dynamic = 'force-dynamic';

interface Seller {
  id: string;
  handle: string;
  displayName: string;
  identityStatus: VerificationStatus;
  phoneStatus: VerificationStatus;
  emailStatus: VerificationStatus;
  score: number | null;
  riskLevel: RiskLevel | null;
}

interface Checklist {
  checklist: {
    key: string; label: string; status: VerificationStatus;
    pointsAvailable: number; actionUrl: string | null;
  }[];
}

export default async function DashboardPage() {
  const seller = await serverFetch<Seller>('/api/v1/sellers/me');
  if (!seller) redirect('/login?next=/dashboard');

  const status = await serverFetch<Checklist>('/api/v1/verification/status');

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-2xl font-bold">Welcome back, {seller.displayName}</h1>
      <p className="text-muted-foreground mt-1">
        Your public page: <code>/seller/{seller.handle}</code>
      </p>

      <div className="mt-8 grid gap-6 md:grid-cols-[auto,1fr]">
        <Card className="flex items-center justify-center p-6">
          <ScoreGauge
            score={seller.score ?? 0}
            riskLevel={seller.riskLevel ?? 'UNKNOWN'}
            size="md"
          />
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Complete your verification</CardTitle>
          </CardHeader>
          <CardContent>
            {status ? (
              <VerificationChecklist items={status.checklist} />
            ) : (
              <p className="text-muted-foreground text-sm">
                Verification status is unavailable right now.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {seller.riskLevel && (
        <div className="mt-6">
          <RiskBadge riskLevel={seller.riskLevel} score={seller.score ?? undefined} />
        </div>
      )}
    </main>
  );
}
