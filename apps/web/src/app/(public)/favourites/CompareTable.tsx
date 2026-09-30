'use client';

import { type PublicListing } from '@/features/marketplace';
import { LISTING_CATEGORY_LABELS, RISK_PRESENTATION, type RiskLevel } from '@trustlens/constants';
import { X } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';

const ROWS: { label: string; render: (l: PublicListing) => React.ReactNode }[] = [
  {
    label: 'Price',
    render: (l) =>
      l.price !== null ? `${l.currency ?? ''} ${l.price.toLocaleString()}` : 'On request',
  },
  { label: 'Condition', render: (l) => l.condition?.replace(/_/g, ' ').toLowerCase() ?? '—' },
  { label: 'Category', render: (l) => (l.category ? LISTING_CATEGORY_LABELS[l.category] : '—') },
  { label: 'Location', render: (l) => (l.area ? `${l.area}, ${l.city}` : (l.city ?? '—')) },
  { label: 'Seller', render: (l) => l.sellerDisplayName },
  {
    label: 'Trust Score',
    render: (l) =>
      l.riskLevel
        ? l.score !== null
          ? `${l.score}/100`
          : RISK_PRESENTATION[l.riskLevel as RiskLevel].label
        : '—',
  },
  { label: 'Identity verified', render: (l) => (l.identityVerified ? 'Yes' : 'No') },
];

/** A real side-by-side of the selected favourites' own listing data - no
 * separate comparison model, just the same fields the card already shows. */
export function CompareTable({
  listings,
  onClose,
  onRemove,
}: {
  listings: PublicListing[];
  onClose: () => void;
  onRemove: (id: string) => void;
}) {
  return (
    <div className="animate-fade-up rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Comparing {listings.length} listings</h2>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Close comparison"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[480px] border-collapse text-sm">
          <thead>
            <tr>
              <th className="w-32 pb-2 text-left text-xs font-medium text-muted-foreground" />
              {listings.map((listing) => (
                <th key={listing.id} className="px-2 pb-2 text-left align-top">
                  <div className="relative aspect-square w-24 overflow-hidden rounded-md border border-border bg-muted">
                    {(listing.thumbnailUrl ?? listing.imageUrl) && (
                      <Image
                        src={listing.thumbnailUrl ?? listing.imageUrl ?? ''}
                        alt={listing.title}
                        fill
                        className="object-cover"
                        unoptimized
                      />
                    )}
                  </div>
                  <Link
                    href={`/listing/${listing.id}`}
                    className="mt-1 block max-w-24 truncate text-xs font-semibold hover:underline"
                  >
                    {listing.title}
                  </Link>
                  <button
                    type="button"
                    onClick={() => onRemove(listing.id)}
                    className="mt-0.5 text-[11px] text-muted-foreground hover:text-destructive"
                  >
                    Remove
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.label} className="border-t border-border/70">
                <td className="py-2 pr-2 text-xs font-medium text-muted-foreground">{row.label}</td>
                {listings.map((listing) => (
                  <td key={listing.id} className="px-2 py-2 text-xs">
                    {row.render(listing)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
