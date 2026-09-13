import { Button } from '@trustlens/ui';
import { Flag } from 'lucide-react';
import Link from 'next/link';

/**
 * The public seller page deliberately carries no internal seller UUID - the
 * PublicTrustScore payload it renders from is the same PII-minimal shape the
 * partner API returns, and adding one here would mean adding one there too.
 * Reporting a seller from this page routes to the existing Report an Issue
 * flow instead, with the handle pre-filled, rather than punching a hole in
 * that boundary for one button.
 */
export function SellerReportButton({ handle }: { handle: string }) {
  return (
    <Button variant="outline" size="sm" asChild>
      <Link href={`/report-issue?seller=${encodeURIComponent(handle)}`}>
        <Flag className="h-4 w-4" aria-hidden="true" />
        Report this seller
      </Link>
    </Button>
  );
}
