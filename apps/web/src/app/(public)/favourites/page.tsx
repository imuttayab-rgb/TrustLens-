'use client';

import { RequireSession } from '@/features/auth';
import { useMyFavorites, useSavedSearches } from '@/features/marketplace';
import { useMyFollows } from '@/features/reputation';
import { cn } from '@trustlens/utils';
import { Heart, Lock, Search, Users } from 'lucide-react';
import { useState } from 'react';
import { FavouriteListingsTab } from './FavouriteListingsTab';
import { FollowedSellersTab } from './FollowedSellersTab';
import { SavedSearchesTab } from './SavedSearchesTab';

type Tab = 'listings' | 'searches' | 'sellers';

const TABS: { key: Tab; label: string }[] = [
  { key: 'listings', label: 'Favourite Listings' },
  { key: 'searches', label: 'Saved Searches' },
  { key: 'sellers', label: 'Followed Sellers' },
];

function FavouritesContent() {
  const [tab, setTab] = useState<Tab>('listings');
  const { data: favorites } = useMyFavorites({ limit: 50 });
  const { data: searches } = useSavedSearches();
  const { data: follows } = useMyFollows();

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
      <h1 className="text-2xl font-bold sm:text-3xl">Your Favourites</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Save listings, follow sellers and bookmark searches you care about.
      </p>

      <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard icon={Heart} value={favorites?.total ?? 0} label="Favourite Listings" />
        <StatCard icon={Search} value={searches?.length ?? 0} label="Saved Searches" />
        <StatCard icon={Users} value={follows?.length ?? 0} label="Followed Sellers" />
      </div>

      <div className="mt-6 flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              'relative px-3 py-2.5 text-sm font-medium transition-colors',
              tab === t.key ? 'text-brand' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {t.label}
            {tab === t.key && (
              <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand" />
            )}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === 'listings' && <FavouriteListingsTab />}
        {tab === 'searches' && <SavedSearchesTab />}
        {tab === 'sellers' && <FollowedSellersTab />}
      </div>

      <div className="mt-8 flex items-start gap-2 rounded-lg border border-border/60 bg-muted/30 p-3 text-sm text-muted-foreground">
        <Lock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <p>
          <span className="font-medium text-foreground">Your favourites are private.</span> Only you
          can see your saved items, searches and followed sellers.
        </p>
      </div>
    </main>
  );
}

function StatCard({
  icon: Icon,
  value,
  label,
}: {
  icon: typeof Heart;
  value: number;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand/10 text-brand">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>
      <div>
        <p className="text-xl font-bold tabular-nums">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

export default function FavouritesPage() {
  return (
    <RequireSession>
      <FavouritesContent />
    </RequireSession>
  );
}
