'use client';

import { BecomeSellerForm, useSeller, useVerificationStatus } from '@/features/seller';
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  RiskBadge,
  ScoreGauge,
  Spinner,
  VerificationChecklist,
} from '@trustlens/ui';
import Link from 'next/link';

export default function DashboardPage() {
  const { data: seller, isPending: sellerLoading } = useSeller();
  const { data: status } = useVerificationStatus();

  if (sellerLoading) {
    return (
      <div className="flex min-h-[40dvh] items-center justify-center">
        <Spinner label="Loading your dashboard" />
      </div>
    );
  }

  if (!seller) {
    return (
      <div className="mx-auto max-w-md space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold">Start selling</h1>
          <p className="text-sm text-muted-foreground">
            Create a seller profile to start earning a Trust Score buyers can check before dealing
            with you.
          </p>
        </div>
        <BecomeSellerForm />
      </div>
    );
  }

  const nextStep = status?.checklist.find((item) => item.status !== 'VERIFIED' && item.actionUrl);

  return (
    <>
      <h1 className="text-2xl font-bold">Welcome back, {seller.displayName}</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Your public page:{' '}
        <Link href={`/seller/${seller.handle}`} className="text-primary hover:underline">
          /seller/{seller.handle}
        </Link>
      </p>

      <div className="mt-8 grid gap-6 md:grid-cols-[auto_1fr]">
        <Card className="flex flex-col items-center justify-center gap-3 p-6">
          <ScoreGauge
            score={seller.score ?? 0}
            riskLevel={seller.riskLevel ?? 'UNKNOWN'}
            size="md"
          />
          {seller.riskLevel && (
            <RiskBadge riskLevel={seller.riskLevel} score={seller.score ?? undefined} />
          )}
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Complete your verification</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {status ? (
              <VerificationChecklist items={status.checklist} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Verification status is unavailable right now.
              </p>
            )}

            {/* One obvious next action beats four links of equal weight. */}
            {nextStep && (
              <Button asChild className="w-full">
                <Link href={nextStep.actionUrl as string}>
                  Continue: {nextStep.label} (+{nextStep.pointsAvailable})
                </Link>
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      {seller.accountType === 'BUSINESS' && seller.businessVerificationStatus !== 'VERIFIED' && (
        <Card className="mt-6">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6">
            <div>
              <p className="font-medium">Verify your business</p>
              <p className="text-sm text-muted-foreground">
                {seller.businessVerificationStatus === 'PENDING'
                  ? 'Your registration document is with a staff reviewer.'
                  : 'Shows a "Verified business" badge on your storefront.'}
              </p>
            </div>
            {seller.businessVerificationStatus !== 'PENDING' && (
              <Button asChild variant="outline">
                <Link href="/dashboard/verification/business">Verify now</Link>
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      <div className="mt-6">
        <Button variant="outline" asChild>
          <Link href="/dashboard/trust-score">See your full score breakdown</Link>
        </Button>
      </div>
    </>
  );
}
