'use client';

import { useListings } from '@/features/listings';
import { Alert, Button, Card, CardContent, Spinner } from '@trustlens/ui';
import { LISTING_CATEGORY_LABELS } from '@trustlens/constants';
import Link from 'next/link';

const STATUS_TONE: Record<string, string> = {
  ACTIVE: 'text-risk-low bg-risk-low-bg',
  ANALYSING: 'text-risk-medium bg-risk-medium-bg',
  FLAGGED: 'text-risk-high bg-risk-high-bg',
  DRAFT: 'text-risk-unknown bg-risk-unknown-bg',
  REMOVED: 'text-risk-unknown bg-risk-unknown-bg',
  EXPIRED: 'text-risk-unknown bg-risk-unknown-bg',
};

export default function ListingsPage() {
  const { data, isPending } = useListings();

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Your selling</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Everything you sell is analysed for scam patterns, and the result feeds your Trust
            Score.
          </p>
        </div>
        <Button asChild>
          <Link href="/dashboard/listings/new">Sell something</Link>
        </Button>
      </div>

      {isPending ? (
        <div className="mt-10 flex justify-center">
          <Spinner label="Loading" />
        </div>
      ) : !data || data.items.length === 0 ? (
        <Alert tone="info" title="You're not selling anything yet" className="mt-8">
          Sell your first item to have it checked. Sellers with nothing for sale cannot earn the
          listing points.
        </Alert>
      ) : (
        <ul className="mt-8 space-y-3">
          {data.items.map((listing) => (
            <li key={listing.id}>
              <Card>
                <CardContent className="pt-6">
                  <Link
                    href={`/dashboard/listings/${listing.id}`}
                    className="block rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{listing.title}</p>
                        <p className="mt-0.5 text-sm text-muted-foreground">
                          {listing.category
                            ? LISTING_CATEGORY_LABELS[listing.category]
                            : 'Uncategorised'}
                          {listing.price !== null &&
                            ` · ${listing.currency ?? ''} ${listing.price.toLocaleString()}`}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${
                          STATUS_TONE[listing.status] ?? ''
                        }`}
                      >
                        {listing.status}
                      </span>
                    </div>
                  </Link>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
