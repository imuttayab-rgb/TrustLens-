/** Reusable UI rendering and interaction component: StartAuctionCard. */
'use client';

import { toApiError } from '@trustlens/api-client';
import {
  Alert,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  fieldAria,
  Input,
} from '@trustlens/ui';
import { formatDateTime } from '@trustlens/utils';
import { useState } from 'react';
import { useAuctionForListing, useCreateAuction } from '../hooks/use-commerce';

const DURATION_OPTIONS = [
  { label: '24 hours', hours: 24 },
  { label: '3 days', hours: 72 },
  { label: '7 days', hours: 168 },
  { label: '14 days', hours: 336 },
];

function formatMoney(amount: number, currency: string) {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

/**
 * Lets a seller list an ACTIVE listing as an auction instead of - or after -
 * a fixed price. Sits on the dashboard listing page next to risk analysis;
 * once an auction is live it's read-only here (bidding happens on the
 * public listing page via `AuctionPanel`).
 */
export function StartAuctionCard({
  listingId,
  listingStatus,
  suggestedPrice,
  currency,
}: {
  listingId: string;
  listingStatus: string;
  suggestedPrice: number | null;
  currency: string | null;
}) {
  const { data: auction, isPending } = useAuctionForListing(listingId);
  const createAuction = useCreateAuction(listingId);
  const [showForm, setShowForm] = useState(false);
  const [startingPrice, setStartingPrice] = useState(suggestedPrice ? String(suggestedPrice) : '');
  const [durationHours, setDurationHours] = useState(168);
  const [reservePrice, setReservePrice] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (isPending) return null;

  async function handleCreate() {
    const price = Number(startingPrice);
    if (!Number.isFinite(price) || price <= 0) {
      setError('Enter a starting price greater than zero.');
      return;
    }
    const reserve = reservePrice.trim() ? Number(reservePrice) : undefined;
    if (reserve !== undefined && (!Number.isFinite(reserve) || reserve < price)) {
      setError("The reserve price can't be below the starting price.");
      return;
    }
    setError(null);
    try {
      await createAuction.mutateAsync({
        startingPrice: price,
        currency: currency ?? 'PKR',
        durationHours,
        ...(reserve !== undefined ? { reservePrice: reserve } : {}),
      });
      setShowForm(false);
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  const activeAuction = auction && auction.status === 'ACTIVE' ? auction : null;

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>Auction</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {activeAuction ? (
          <div className="space-y-1 text-sm">
            <p className="font-medium">
              Live · current bid{' '}
              {formatMoney(
                activeAuction.currentPrice ?? activeAuction.startingPrice,
                activeAuction.currency,
              )}{' '}
              · {activeAuction.bidCount} {activeAuction.bidCount === 1 ? 'bid' : 'bids'}
            </p>
            <p className="text-muted-foreground">Ends {formatDateTime(activeAuction.endsAt)}</p>
          </div>
        ) : auction && auction.status === 'ENDED' ? (
          <div className="space-y-2 text-sm">
            <p className="text-muted-foreground">
              Last auction ended {formatDateTime(auction.endedAt ?? auction.endsAt)}
              {auction.winningBidId ? ' with a winner.' : ' without a winner.'}
            </p>
            {listingStatus === 'ACTIVE' && (
              <Button size="sm" variant="outline" onClick={() => setShowForm(true)}>
                Start a new auction
              </Button>
            )}
          </div>
        ) : listingStatus !== 'ACTIVE' ? (
          <p className="text-sm text-muted-foreground">
            This item needs to be active to start an auction.
          </p>
        ) : showForm ? (
          <div className="space-y-2">
            <Field htmlFor="auction-starting-price" label="Starting price" required>
              <Input
                {...fieldAria('auction-starting-price')}
                type="number"
                min="0.01"
                step="0.01"
                value={startingPrice}
                onChange={(event) => setStartingPrice(event.target.value)}
                placeholder="0.00"
              />
            </Field>
            <Field htmlFor="auction-duration" label="Duration">
              <select
                id="auction-duration"
                value={durationHours}
                onChange={(event) => setDurationHours(Number(event.target.value))}
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              >
                {DURATION_OPTIONS.map((option) => (
                  <option key={option.hours} value={option.hours}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              htmlFor="auction-reserve"
              label="Reserve price"
              hint="Optional - the lowest you'll accept"
            >
              <Input
                {...fieldAria('auction-reserve')}
                type="number"
                min="0.01"
                step="0.01"
                value={reservePrice}
                onChange={(event) => setReservePrice(event.target.value)}
                placeholder="No reserve"
              />
            </Field>
            {error && <Alert tone="error">{error}</Alert>}
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={createAuction.isPending}
                onClick={() => void handleCreate()}
              >
                {createAuction.isPending ? 'Starting…' : 'Start auction'}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button variant="outline" className="w-full" onClick={() => setShowForm(true)}>
            Sell this by auction instead
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
