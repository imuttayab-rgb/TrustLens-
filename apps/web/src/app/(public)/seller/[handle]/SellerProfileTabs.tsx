/** Next.js route/layout composition for (public)/seller/[handle]: SellerProfileTabs. */
'use client';

import { ListingCard, type PublicListing } from '@/features/marketplace';
import { SignalBreakdown, type SignalRow } from '@trustlens/ui';
import { cn, formatRelative } from '@trustlens/utils';
import { useState } from 'react';

interface PublicReview {
  id: string;
  rating: number;
  comment: string | null;
  createdAt: string;
}

type Tab = 'active' | 'sold' | 'reviews' | 'report';

export function SellerProfileTabs({
  activeListings,
  pastListings,
  reviews,
  reviewSummary,
  signals,
}: {
  activeListings: PublicListing[];
  pastListings: PublicListing[];
  reviews: PublicReview[];
  reviewSummary: { averageRating: number | null; reviewCount: number };
  signals: SignalRow[];
}) {
  const [tab, setTab] = useState<Tab>('active');

  const tabs: { key: Tab; label: string }[] = [
    { key: 'active', label: `Active Listings (${activeListings.length})` },
    { key: 'sold', label: `Sold (${pastListings.length})` },
    { key: 'reviews', label: `Reviews (${reviewSummary.reviewCount})` },
    { key: 'report', label: 'Trust Report' },
  ];

  return (
    <div>
      <div className="flex gap-1 overflow-x-auto border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              'relative shrink-0 whitespace-nowrap px-3 py-2.5 text-sm font-medium transition-colors',
              tab === t.key ? 'text-brand' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {t.label}
            {tab === t.key && (
              <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand" />
            )}
          </button>
        ))}
      </div>

      <div className="mt-5 animate-fade-in">
        {tab === 'active' &&
          (activeListings.length > 0 ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {activeListings.map((listing) => (
                <ListingCard key={listing.id} listing={listing} />
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No active listings right now.
            </p>
          ))}

        {tab === 'sold' &&
          (pastListings.length > 0 ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {pastListings.map((listing) => (
                <ListingCard key={listing.id} listing={listing} />
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No past deals to show yet.
            </p>
          ))}

        {tab === 'reviews' &&
          (reviews.length > 0 ? (
            <div className="space-y-3">
              {reviews.map((review) => (
                <div key={review.id} className="rounded-lg border border-border p-3 text-sm">
                  <div className="flex items-center gap-2">
                    <div className="flex" aria-label={`${review.rating} out of 5 stars`}>
                      {Array.from({ length: 5 }, (_, i) => (
                        <span
                          key={i}
                          className={
                            i < review.rating ? 'text-amber-500' : 'text-muted-foreground/40'
                          }
                          aria-hidden="true"
                        >
                          ★
                        </span>
                      ))}
                    </div>
                    {/* Every review is tied to a completed transaction - not a
                        claim added for this page. */}
                    <span className="rounded-full bg-risk-low-bg px-2 py-0.5 text-[11px] font-medium text-risk-low">
                      Verified transaction
                    </span>
                  </div>
                  {review.comment && (
                    <p className="mt-1.5 text-muted-foreground">{review.comment}</p>
                  )}
                  <p className="mt-1 text-xs text-muted-foreground">
                    {formatRelative(review.createdAt)}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">No reviews yet.</p>
          ))}

        {tab === 'report' && <SignalBreakdown signals={signals} />}
      </div>
    </div>
  );
}
