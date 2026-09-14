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
import { ListingCard, type PublicListing } from '@/features/marketplace';
import { SellerReportButton } from '@/features/moderation';
import { FollowButton } from '@/features/reputation';
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
import { Building2 } from 'lucide-react';
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

interface PublicReview {
  id: string;
  rating: number;
  comment: string | null;
  createdAt: string;
}

interface SellerReviews {
  items: PublicReview[];
  summary: { averageRating: number | null; reviewCount: number };
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

/**
 * The storefront's listings grid (MKT-04). Reuses the same public catalog
 * search the browse page uses, filtered to this seller's handle - same
 * PII-free projection, no separate read path. Unlike the anonymous
 * catalog, a seller_handle-filtered search also returns their
 * RESERVED/SOLD listings (a deliberate storefront-only broadening, see
 * `include_sold` in browse_public.py), so this doubles as the sold
 * history the spec asks for.
 */
async function getSellerListings(handle: string): Promise<PublicListing[]> {
  return (
    (await serverFetch<PublicListing[]>(
      `/api/v1/public/listings?seller=${encodeURIComponent(handle)}&limit=12`,
    )) ?? []
  );
}

async function getSellerReviews(handle: string): Promise<SellerReviews> {
  return (
    (await serverFetch<SellerReviews>(
      `/api/v1/public/sellers/${encodeURIComponent(handle)}/reviews`,
    )) ?? { items: [], summary: { averageRating: null, reviewCount: 0 } }
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
  const [score, listings, reviews] = await Promise.all([
    getScore(handle),
    getSellerListings(handle),
    getSellerReviews(handle),
  ]);
  if (!score) notFound();

  const activeListings = listings.filter((l) => l.status === 'ACTIVE');
  const pastListings = listings.filter((l) => l.status !== 'ACTIVE');

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
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
      <header className="flex flex-col items-center gap-3 text-center">
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
        <div className="space-y-1">
          <h1 className="text-xl font-bold sm:text-2xl">{handle}</h1>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <RiskBadge riskLevel={score.riskLevel} />
            {score.verifications.business === 'VERIFIED' && (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                <Building2 className="h-3 w-3" aria-hidden="true" />
                Verified business
              </span>
            )}
          </div>
        </div>
        <p className="text-xs text-muted-foreground sm:text-sm">
          Last checked {formatDateTime(score.computedAt)} · scoring model {score.modelVersion}
        </p>
        <div className="flex items-center gap-2">
          <FollowButton handle={handle} />
          <SellerReportButton handle={handle} />
        </div>
      </header>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>Why this score</CardTitle>
        </CardHeader>
        <CardContent>
          <SignalBreakdown signals={signals} />
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Checks completed</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {Object.entries(score.verifications).map(([key, value]) => (
              <div key={key} className="rounded-lg border border-border p-3">
                <dt className="text-sm capitalize text-muted-foreground">{key}</dt>
                <dd className="mt-0.5 font-medium">{value.replace(/_/g, ' ').toLowerCase()}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      {activeListings.length > 0 && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Active listings ({activeListings.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {activeListings.map((listing) => (
                <ListingCard key={listing.id} listing={listing} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {pastListings.length > 0 && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Past deals ({pastListings.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {pastListings.map((listing) => (
                <ListingCard key={listing.id} listing={listing} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {reviews.summary.reviewCount > 0 && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>
              Reviews ({reviews.summary.reviewCount})
              {reviews.summary.averageRating !== null &&
                ` · ${reviews.summary.averageRating.toFixed(1)} avg`}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {reviews.items.map((review) => (
              <div key={review.id} className="rounded-lg border border-border p-3 text-sm">
                <div className="flex" aria-label={`${review.rating} out of 5 stars`}>
                  {Array.from({ length: 5 }, (_, i) => (
                    <span
                      key={i}
                      className={i < review.rating ? 'text-amber-500' : 'text-muted-foreground/40'}
                      aria-hidden="true"
                    >
                      ★
                    </span>
                  ))}
                </div>
                {review.comment && <p className="mt-1 text-muted-foreground">{review.comment}</p>}
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatDateTime(review.createdAt)}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <section className="mt-8 rounded-lg border border-border/60 bg-muted/30 p-4 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">About Trust Scores</p>
        <p className="mt-1">
          A Trust Score reflects verified identity, contact, device and listing checks — not a
          personal endorsement. Always inspect goods before paying. Never send advance payment to
          someone you have not met in person.
        </p>
        <p className="mt-2 text-xs">
          Powered by TrustLens · Scores refresh automatically when new verifications complete.
        </p>
      </section>
    </main>
  );
}
