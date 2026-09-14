'use client';

import { useSession } from '@/lib/auth/use-session';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input } from '@trustlens/ui';
import { useEffect, useState } from 'react';
import { useAuctionBids, useAuctionForListing, usePlaceBid, type Bid } from '../hooks/use-commerce';

function formatMoney(amount: number, currency: string) {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

function useCountdown(endsAt: string) {
  const [remaining, setRemaining] = useState(() => new Date(endsAt).getTime() - Date.now());
  useEffect(() => {
    const id = setInterval(() => setRemaining(new Date(endsAt).getTime() - Date.now()), 1_000);
    return () => clearInterval(id);
  }, [endsAt]);
  return remaining;
}

function formatRemaining(ms: number): string {
  if (ms <= 0) return 'Ending…';
  const totalMinutes = Math.floor(ms / 60_000);
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days}d ${hours}h left`;
  if (hours > 0) return `${hours}h ${minutes}m left`;
  return `${minutes}m left`;
}

/**
 * Bidding UI for a listing that's up for auction (AUC-01). Only rendered for
 * a signed-in viewer - the auction endpoints require a session, matching the
 * rest of this pass's "no anonymous auction browsing" scope decision - so an
 * anonymous visitor just sees the normal fixed-price listing page underneath.
 */
export function AuctionPanel({ listingId }: { listingId: string }) {
  const { data: session } = useSession();
  const { data: auction } = useAuctionForListing(session ? listingId : null);
  const { data: bids } = useAuctionBids(
    auction?.status === 'ACTIVE' ? (auction?.id ?? null) : null,
  );
  const placeBid = usePlaceBid(auction?.id ?? '');
  const [amount, setAmount] = useState('');
  const [error, setError] = useState<string | null>(null);
  const remaining = useCountdown(auction?.endsAt ?? new Date().toISOString());

  if (!auction || auction.status === 'CANCELLED') return null;

  const isSeller = session?.id === auction.sellerId;
  const currentPrice = auction.currentPrice ?? auction.startingPrice;
  const minNextBid = auction.currentPrice ? auction.currentPrice + 1 : auction.startingPrice;

  async function handleBid() {
    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed < minNextBid) {
      setError(`Bid at least ${formatMoney(minNextBid, auction!.currency)}.`);
      return;
    }
    setError(null);
    try {
      await placeBid.mutateAsync(parsed);
      setAmount('');
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  return (
    <div className="mt-4 rounded-lg border border-brand bg-brand/5 p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {auction.status === 'ACTIVE' ? 'Live auction' : 'Auction ended'}
          </p>
          <p className="text-2xl font-semibold">{formatMoney(currentPrice, auction.currency)}</p>
          <p className="text-sm text-muted-foreground">
            {auction.bidCount} {auction.bidCount === 1 ? 'bid' : 'bids'}
          </p>
        </div>
        {auction.status === 'ACTIVE' && (
          <p className="text-sm font-medium">{formatRemaining(remaining)}</p>
        )}
      </div>

      {auction.status === 'ENDED' && (
        <p className="mt-2 text-sm text-muted-foreground">
          {auction.winningBidId
            ? 'This auction has a winner.'
            : "This auction ended without meeting the seller's reserve."}
        </p>
      )}

      {auction.status === 'ACTIVE' && !isSeller && (
        <div className="mt-3 space-y-2">
          <Field
            htmlFor="bid-amount"
            label={`Your bid (min ${formatMoney(minNextBid, auction.currency)})`}
          >
            <Input
              {...fieldAria('bid-amount')}
              type="number"
              min={minNextBid}
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              placeholder={minNextBid.toFixed(2)}
            />
          </Field>
          {error && <Alert tone="error">{error}</Alert>}
          <Button
            className="w-full"
            disabled={placeBid.isPending || !amount}
            onClick={() => void handleBid()}
          >
            {placeBid.isPending ? 'Placing bid…' : 'Place bid'}
          </Button>
        </div>
      )}
      {auction.status === 'ACTIVE' && isSeller && (
        <p className="mt-3 text-sm text-muted-foreground">This is your auction.</p>
      )}

      {bids && bids.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-muted-foreground">
            Bid history ({bids.length})
          </summary>
          <ul className="mt-2 space-y-1">
            {bids.map((bid: Bid) => (
              <li key={bid.id} className="flex justify-between text-muted-foreground">
                <span>{bid.bidderId === session?.id ? 'You' : 'Bidder'}</span>
                <span>{formatMoney(bid.amount, auction.currency)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
