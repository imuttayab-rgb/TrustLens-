'use client';

import { useReviewQueue } from '@/features/review';
import { useSession } from '@/lib/auth/use-session';
import { Card, CardContent, Spinner } from '@trustlens/ui';
import Link from 'next/link';

export default function AdminOverviewPage() {
  const { data: user } = useSession();
  const { data: cases, isPending } = useReviewQueue();

  const open = (cases ?? []).filter((c) => c.status === 'QUEUED').length;
  const claimed = (cases ?? []).filter((c) => c.status === 'ASSIGNED').length;
  const decided = (cases ?? []).filter(
    (c) => c.status === 'APPROVED' || c.status === 'REJECTED',
  ).length;

  return (
    <main className="mx-auto max-w-3xl p-6 sm:p-8">
      <h1 className="text-2xl font-bold">
        {user ? `Welcome, ${user.fullName}` : 'Admin overview'}
      </h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Every decision you record here is written to the audit log against your account.
      </p>

      {isPending ? (
        <div className="mt-10 flex justify-center">
          <Spinner label="Loading queue counts" />
        </div>
      ) : (
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {[
            { label: 'Waiting', value: open, tone: 'text-risk-medium' },
            { label: 'Claimed', value: claimed, tone: 'text-foreground' },
            { label: 'Decided', value: decided, tone: 'text-risk-low' },
          ].map((stat) => (
            <Card key={stat.label}>
              <CardContent className="pt-6">
                <p className={`text-3xl font-bold tabular-nums ${stat.tone}`}>{stat.value}</p>
                <p className="mt-1 text-sm text-muted-foreground">{stat.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Link
        href="/reviews"
        className="mt-8 inline-block text-sm font-medium text-primary underline-offset-4 hover:underline"
      >
        Open the review queue →
      </Link>
    </main>
  );
}
