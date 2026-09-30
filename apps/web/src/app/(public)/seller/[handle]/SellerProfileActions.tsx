'use client';

import { useSession } from '@/lib/auth/use-session';
import { Button } from '@trustlens/ui';
import { MessageCircle, Share2 } from 'lucide-react';
import { useRouter } from 'next/navigation';

/**
 * Share is a plain link-share (native share sheet, or clipboard) - nothing
 * seller-specific to fetch. "Chat Safely" reuses the existing listing-scoped
 * message flow (messaging has no seller-only, listing-less conversation
 * type), so it opens a conversation about the seller's own most recent
 * active listing rather than pretending there's a generic contact form.
 */
export function SellerProfileActions({
  handle,
  primaryListingId,
}: {
  handle: string;
  primaryListingId: string | null;
}) {
  const router = useRouter();
  const { data: session } = useSession();

  async function share() {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({ title: `${handle} on TrustLens`, url });
      } catch {
        // Cancelled - not an error.
      }
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      // Clipboard access can be denied; no good fallback UI here.
    }
  }

  function chatSafely() {
    if (!primaryListingId) return;
    if (!session) {
      router.push(`/login?next=${encodeURIComponent(`/seller/${handle}`)}`);
      return;
    }
    router.push(`/dashboard/messages/new?listingId=${primaryListingId}`);
  }

  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" onClick={() => void share()}>
        <Share2 className="h-4 w-4" aria-hidden="true" />
        Share
      </Button>
      {primaryListingId && (
        <Button size="sm" onClick={chatSafely}>
          <MessageCircle className="h-4 w-4" aria-hidden="true" />
          Chat Safely
        </Button>
      )}
    </div>
  );
}
