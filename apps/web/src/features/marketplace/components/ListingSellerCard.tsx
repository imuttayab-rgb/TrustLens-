import { ListingDetailActions } from './ListingDetailActions';
import { AuctionPanel } from '@/features/commerce';
import { type RiskLevel } from '@trustlens/constants';
import { RiskBadge, ScoreGauge } from '@trustlens/ui';
import { Building2, Check, IdCard, Mail, Phone, ShieldCheck, Star } from 'lucide-react';
import Link from 'next/link';

const VERIFICATION_ITEMS: { key: string; label: string; icon: typeof IdCard }[] = [
  { key: 'identity', label: 'Identity verified', icon: IdCard },
  { key: 'phone', label: 'Phone verified', icon: Phone },
  { key: 'email', label: 'Email verified', icon: Mail },
  { key: 'business', label: 'Verified business', icon: Building2 },
];

/**
 * The seller trust card on a listing page - the same public score payload
 * `/seller/[handle]` renders in full, condensed to what a buyer needs before
 * messaging: the score, what's actually verified, and a link to the full
 * report rather than a re-derived breakdown (MKT-05).
 */
export function ListingSellerCard({
  sellerHandle,
  sellerDisplayName,
  listingId,
  listingTitle,
  score,
  activeListingsCount,
  reviews,
}: {
  sellerHandle: string;
  sellerDisplayName: string;
  listingId: string;
  listingTitle: string;
  score: {
    score: number;
    riskLevel: RiskLevel;
    verifications: Record<string, string>;
    memberSince: string;
  };
  activeListingsCount: number;
  reviews: { averageRating: number | null; reviewCount: number };
}) {
  const memberSinceYear = score.memberSince ? new Date(score.memberSince).getFullYear() : null;

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand/10 text-lg font-bold text-brand">
          {sellerDisplayName.charAt(0).toUpperCase()}
        </div>
        <div className="min-w-0">
          <Link
            href={`/seller/${encodeURIComponent(sellerHandle)}`}
            className="flex items-center gap-1.5 truncate font-semibold hover:underline"
          >
            <span className="truncate">{sellerDisplayName}</span>
            {score.verifications.identity === 'VERIFIED' && (
              <ShieldCheck
                className="h-4 w-4 shrink-0 text-risk-low"
                aria-label="Identity verified"
              />
            )}
          </Link>
          <p className="truncate text-sm text-muted-foreground">@{sellerHandle}</p>
        </div>
      </div>

      <div className="mt-5 flex items-center gap-4 border-t border-border pt-5">
        <ScoreGauge score={score.score} riskLevel={score.riskLevel} size="sm" />
        <div className="min-w-0 flex-1 border-l border-border pl-4">
          <p className="text-sm font-bold">Trust Score</p>
          <RiskBadge riskLevel={score.riskLevel} className="mt-1" />
          <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
            Based on verified identity, activity and community feedback.
          </p>
        </div>
      </div>

      <ul className="mt-4 space-y-1.5 border-t border-border pt-4">
        {VERIFICATION_ITEMS.filter((item) => item.key in score.verifications).map((item) => {
          const Icon = item.icon;
          const done = score.verifications[item.key] === 'VERIFIED';
          return (
            <li key={item.key} className="flex items-center gap-2 text-sm">
              <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate text-muted-foreground">{item.label}</span>
              <span
                className={
                  done
                    ? 'grid h-4 w-4 shrink-0 place-items-center rounded-full bg-risk-low/15'
                    : 'grid h-4 w-4 shrink-0 place-items-center rounded-full bg-muted'
                }
              >
                {done && <Check className="h-3 w-3 text-risk-low" aria-hidden="true" />}
              </span>
            </li>
          );
        })}
      </ul>

      <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4 text-center">
        <div>
          <dt className="text-xs text-muted-foreground">Member since</dt>
          <dd className="mt-0.5 text-sm font-semibold">{memberSinceYear ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Listings</dt>
          <dd className="mt-0.5 text-sm font-semibold">{activeListingsCount}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Reviews</dt>
          <dd className="mt-0.5 flex items-center justify-center gap-0.5 text-sm font-semibold">
            {reviews.reviewCount > 0 ? (
              <>
                <Star className="h-3.5 w-3.5 fill-amber-500 text-amber-500" aria-hidden="true" />
                {reviews.averageRating?.toFixed(1)}
              </>
            ) : (
              '—'
            )}
          </dd>
        </div>
      </dl>

      <Link
        href={`/seller/${encodeURIComponent(sellerHandle)}`}
        className="mt-4 block text-center text-sm font-medium text-brand underline-offset-4 hover:underline"
      >
        View full Trust Report →
      </Link>

      <div className="mt-5 border-t border-border pt-5">
        <ListingDetailActions listingId={listingId} title={listingTitle} />
      </div>

      <AuctionPanel listingId={listingId} />
    </div>
  );
}
