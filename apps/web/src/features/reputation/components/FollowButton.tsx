'use client';

import { useSession } from '@/lib/auth/use-session';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button } from '@trustlens/ui';
import { Heart } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useFollowSeller, useMyFollows, useUnfollowSeller } from '../hooks/use-reputation';

/**
 * Follow/unfollow a seller by handle. Deliberately handle-only, never the
 * seller's internal user id - see reputation.py's router docstring for why
 * the public seller page carries no such id at all.
 */
export function FollowButton({ handle }: { handle: string }) {
  const { data: session } = useSession();
  const router = useRouter();
  const { data: follows, isPending } = useMyFollows();
  const followSeller = useFollowSeller();
  const unfollowSeller = useUnfollowSeller();
  const [error, setError] = useState<string | null>(null);

  if (!session) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => router.push(`/login?next=/seller/${encodeURIComponent(handle)}`)}
      >
        <Heart className="h-4 w-4" aria-hidden="true" />
        Follow
      </Button>
    );
  }

  const isFollowing = follows?.includes(handle) ?? false;
  const busy = isPending || followSeller.isPending || unfollowSeller.isPending;

  async function toggle() {
    setError(null);
    try {
      if (isFollowing) {
        await unfollowSeller.mutateAsync(handle);
      } else {
        await followSeller.mutateAsync(handle);
      }
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <Button
        variant={isFollowing ? 'default' : 'outline'}
        size="sm"
        disabled={busy}
        onClick={() => void toggle()}
      >
        <Heart className={isFollowing ? 'h-4 w-4 fill-current' : 'h-4 w-4'} aria-hidden="true" />
        {isFollowing ? 'Following' : 'Follow'}
      </Button>
      {error && (
        <Alert tone="error" className="text-xs">
          {error}
        </Alert>
      )}
    </div>
  );
}
