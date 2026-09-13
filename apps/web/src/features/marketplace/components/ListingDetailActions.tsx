'use client';

import { useSession } from '@/lib/auth/use-session';
import { ReportButton } from '@/features/moderation';
import { Button } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { Heart, MessageCircle } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { useAddFavorite, useFavoriteIds, useRemoveFavorite } from '../hooks/use-favorites';

/** The buyer actions on a listing page - all need a client boundary
 * the rest of the (server-rendered, crawlable) page does not. */
export function ListingDetailActions({ listingId }: { listingId: string }) {
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

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Button
          variant="outline"
          className="flex-1"
          disabled={toggling}
          onClick={toggleFavorite}
          aria-pressed={favorited}
        >
          <Heart
            className={cn('h-4 w-4', favorited && 'fill-current text-destructive')}
            aria-hidden="true"
          />
          {favorited ? 'Saved' : 'Save'}
        </Button>
        <Button
          className="flex-1"
          onClick={() => {
            if (!requireSession()) return;
            router.push(`/dashboard/messages/new?listingId=${listingId}`);
          }}
        >
          <MessageCircle className="h-4 w-4" aria-hidden="true" />
          Message seller
        </Button>
      </div>
      <ReportButton targetType="LISTING" targetId={listingId} label="Report this listing" />
    </div>
  );
}
