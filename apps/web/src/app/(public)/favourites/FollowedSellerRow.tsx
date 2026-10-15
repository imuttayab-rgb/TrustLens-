/** Next.js route/layout composition for (public)/favourites: FollowedSellerRow. */
'use client';

import { RiskBadge } from '@trustlens/ui';
import { ShieldCheck } from 'lucide-react';
import Link from 'next/link';
import { useSellerScore, useUnfollowSeller } from '@/features/reputation';

export function FollowedSellerRow({ handle }: { handle: string }) {
  const { data: score, isPending } = useSellerScore(handle);
  const unfollow = useUnfollowSeller();

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand/10 text-sm font-bold text-brand">
        {handle.charAt(0).toUpperCase()}
      </div>
      <div className="min-w-0 flex-1">
        <Link
          href={`/seller/${encodeURIComponent(handle)}`}
          className="flex items-center gap-1.5 truncate text-sm font-semibold hover:underline"
        >
          <span className="truncate">@{handle}</span>
          {score?.riskLevel === 'LOW' && (
            <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-risk-low" aria-hidden="true" />
          )}
        </Link>
        {isPending ? (
          <span className="text-xs text-muted-foreground">Loading trust score…</span>
        ) : (
          score && <RiskBadge riskLevel={score.riskLevel} score={score.score} className="mt-1" />
        )}
      </div>
      <button
        type="button"
        onClick={() => unfollow.mutate(handle)}
        disabled={unfollow.isPending}
        className="shrink-0 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive disabled:opacity-60"
      >
        Unfollow
      </button>
    </div>
  );
}
