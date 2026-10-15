/** Reusable UI rendering and interaction component: ListingDetailActions. */
'use client';

import { useSession } from '@/lib/auth/use-session';
import { ReportButton } from '@/features/moderation';
import { Button } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { Handshake, Heart, MapPin, MessageCircle, Share2 } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { useAddFavorite, useFavoriteIds, useRemoveFavorite } from '../hooks/use-favorites';

/** The buyer actions on a listing page - all need a client boundary
 * the rest of the (server-rendered, crawlable) page does not. */
export function ListingDetailActions({ listingId, title }: { listingId: string; title: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: session } = useSession();
  const { data: favoriteIds } = useFavoriteIds();
  const addFavorite = useAddFavorite();
  const removeFavorite = useRemoveFavorite();
  const favorited = favoriteIds?.has(listingId) ?? false;
  const toggling =
    (addFavorite.isPending && addFavorite.variables === listingId) ||
    (removeFavorite.isPending && removeFavorite.variables === listingId);

  function requireSession(): boolean {
    if (session) return true;
    router.push(`/login?next=${encodeURIComponent(pathname)}`);
    return false;
  }

  function toggleFavorite() {
    if (!requireSession()) return;
    if (favorited) removeFavorite.mutate(listingId);
    else addFavorite.mutate(listingId);
  }

  async function share() {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
      } catch {
        // The user cancelled the native share sheet - not an error.
      }
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      // Clipboard access can be denied; no good fallback UI here.
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Button
          className="flex-1 transition-transform duration-150 hover:scale-[1.02] active:scale-[0.98]"
          onClick={() => {
            if (!requireSession()) return;
            router.push(`/messages/new?listingId=${listingId}`);
          }}
        >
          <MessageCircle className="h-4 w-4" aria-hidden="true" />
          Chat Safely
        </Button>
        <Button
          variant="outline"
          className="flex-1 transition-transform duration-150 hover:scale-[1.02] active:scale-[0.98]"
          onClick={() => {
            if (!requireSession()) return;
            router.push(`/messages/new?listingId=${listingId}&intent=offer`);
          }}
        >
          <Handshake className="h-4 w-4" aria-hidden="true" />
          Make an Offer
        </Button>
      </div>

      <Button
        variant="outline"
        className="w-full transition-transform duration-150 hover:scale-[1.01] active:scale-[0.98]"
        onClick={() => {
          if (!requireSession()) return;
          router.push(`/messages/new?listingId=${listingId}&intent=safemeet`);
        }}
      >
        <MapPin className="h-4 w-4" aria-hidden="true" />
        Propose SafeMeet
      </Button>

      <div className="flex items-center justify-center gap-4 pt-1 text-sm">
        <button
          type="button"
          onClick={toggleFavorite}
          disabled={toggling}
          aria-pressed={favorited}
          className="flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-60"
        >
          <Heart
            className={cn('h-4 w-4', favorited && 'fill-current text-destructive')}
            aria-hidden="true"
          />
          {favorited ? 'Saved' : 'Add to Favourites'}
        </button>
        <button
          type="button"
          onClick={() => void share()}
          className="flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-foreground"
        >
          <Share2 className="h-4 w-4" aria-hidden="true" />
          Share
        </button>
        <ReportButton targetType="LISTING" targetId={listingId} label="Report" />
      </div>
    </div>
  );
}
