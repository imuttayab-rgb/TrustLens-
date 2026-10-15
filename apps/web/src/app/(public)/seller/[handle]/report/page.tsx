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
import { NearbyVenues, type PublicListing } from '@/features/marketplace';
import { SellerReportButton } from '@/features/moderation';
import { FollowButton } from '@/features/reputation';
import { serverFetch } from '@/lib/api/server';
import { type RiskLevel, SIGNAL_CATEGORIES, type SignalCategory } from '@trustlens/constants';
import { RiskBadge, ScoreGauge, type SignalRow } from '@trustlens/ui';
import { Building2, Calendar, IdCard, Mail, MapPin, Phone, Star, Users } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { SellerProfileActions } from '../SellerProfileActions';
import { SellerProfileTabs } from '../SellerProfileTabs';

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
  memberSince: string;
  bio: string | null;
  city: string | null;
  followerCount: number;
  completedSales: number;
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

const VERIFICATION_ITEMS: { key: string; label: string; icon: typeof IdCard }[] = [
  { key: 'identity', label: 'Identity verified', icon: IdCard },
  { key: 'phone', label: 'Phone verified', icon: Phone },
  { key: 'email', label: 'Email verified', icon: Mail },
  { key: 'business', label: 'Business verified', icon: Building2 },
];

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
  // Not on the PII-free score payload by design (the partner API shares the
  // same schema) - a listing already carries the seller's own chosen
  // storefront name, so this borrows it rather than adding one there.
  const displayName = listings[0]?.sellerDisplayName ?? handle;

  // The public payload carries reasons, not raw signal rows - it is
  // deliberately PII-free. Map them into the shared breakdown shape.
  const signals: SignalRow[] = score.reasons.map((reason) => ({
    code: reason.code,
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

  const memberSinceYear = score.memberSince ? new Date(score.memberSince).getFullYear() : null;
  const isBusiness = score.verifications.business === 'VERIFIED';

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-1.5 text-sm text-muted-foreground"
      >
        <Link href="/" className="hover:text-foreground hover:underline">
          Home
        </Link>
        <span aria-hidden="true">/</span>
        <Link href="/browse" className="hover:text-foreground hover:underline">
          Sellers
        </Link>
        <span aria-hidden="true">/</span>
        <span className="text-foreground">{displayName}</span>
      </nav>

      <div className="mt-4 grid gap-6 rounded-xl border border-border bg-card p-6 shadow-sm lg:grid-cols-[auto_1fr_auto]">
        <div className="flex items-center gap-4 lg:flex-col lg:items-start lg:justify-center">
          <div className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-brand/10 text-2xl font-bold text-brand">
            {displayName.charAt(0).toUpperCase()}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-bold sm:text-2xl">{displayName}</h1>
              {isBusiness && (
                <span className="inline-flex items-center gap-1 rounded-full bg-brand/10 px-2 py-0.5 text-xs font-medium text-brand">
                  <Building2 className="h-3 w-3" aria-hidden="true" />
                  Business Seller
                </span>
              )}
            </div>
            <p className="text-sm text-muted-foreground">@{handle}</p>
            <div className="mt-1.5 space-y-0.5 text-xs text-muted-foreground">
              {score.city && (
                <p className="flex items-center gap-1">
                  <MapPin className="h-3 w-3" aria-hidden="true" />
                  {score.city}
                </p>
              )}
              {memberSinceYear && (
                <p className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" aria-hidden="true" />
                  Member since {memberSinceYear}
                </p>
              )}
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <FollowButton handle={handle} />
              <SellerProfileActions
                handle={handle}
                primaryListingId={activeListings[0]?.id ?? null}
              />
            </div>
          </div>
        </div>

        <div className="flex flex-col items-center gap-4 border-t border-border pt-6 sm:flex-row sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0">
          <ScoreGauge score={score.score} riskLevel={score.riskLevel} size="md" />
          <div className="min-w-0 flex-1 text-center sm:text-left">
            <p className="text-base font-bold">Trust Score</p>
            <RiskBadge riskLevel={score.riskLevel} className="mt-1" />
            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
              Based on verified identity, activity and community feedback.
              {score.unavailableSignals.length > 0 &&
                ` ${score.unavailableSignals.length} check(s) could not be completed.`}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2 border-t border-border pt-6 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
          {VERIFICATION_ITEMS.filter((item) => item.key in score.verifications).map((item) => {
            const Icon = item.icon;
            const done = score.verifications[item.key] === 'VERIFIED';
            return (
              <div key={item.key} className="flex items-center gap-2 text-sm">
                <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="min-w-0 flex-1 truncate text-muted-foreground">{item.label}</span>
                <span
                  className={
                    done
                      ? 'h-2 w-2 shrink-0 rounded-full bg-risk-low'
                      : 'h-2 w-2 shrink-0 rounded-full bg-muted-foreground/30'
                  }
                  aria-hidden="true"
                />
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand/10 text-brand">
            <Star className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <p className="text-lg font-bold tabular-nums">
              {reviews.summary.averageRating !== null
                ? reviews.summary.averageRating.toFixed(1)
                : '—'}
            </p>
            <p className="text-xs text-muted-foreground">
              Rating {reviews.summary.reviewCount > 0 && `(${reviews.summary.reviewCount})`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand/10 text-brand">
            <Building2 className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <p className="text-lg font-bold tabular-nums">{score.completedSales}</p>
            <p className="text-xs text-muted-foreground">Completed sales</p>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand/10 text-brand">
            <Users className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <p className="text-lg font-bold tabular-nums">{score.followerCount}</p>
            <p className="text-xs text-muted-foreground">Followers</p>
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0">
          <SellerProfileTabs
            activeListings={activeListings}
            pastListings={pastListings}
            reviews={reviews.items}
            reviewSummary={reviews.summary}
            signals={signals}
          />
        </div>

        <div className="space-y-5 lg:sticky lg:top-20 lg:self-start">
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-sm font-semibold">About this seller</h2>
            {score.bio ? (
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{score.bio}</p>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                This seller hasn&apos;t added a storefront description yet.
              </p>
            )}
            <div className="mt-3">
              <SellerReportButton handle={handle} />
            </div>
          </div>

          {score.city && (
            <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold">
                <MapPin className="h-4 w-4 text-brand" aria-hidden="true" />
                SafeMeet
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Meet in a public place. Never pay before you inspect the item.
              </p>
              <NearbyVenues city={score.city} />
            </div>
          )}
        </div>
      </div>

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
