/** Ownerads module; defines OwnerAds. */
'use client';
import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Image from 'next/image';
import Link from 'next/link';
import { Alert, Button, Spinner } from '@trustlens/ui';
import { MapPin, Search, ImageOff } from 'lucide-react';
import { useProfileAds } from './hooks';
import { profileRequest } from './api';
const LABELS: Record<string, string> = {
  ACTIVE: 'Active',
  PAUSED: 'Paused',
  SOLD: 'Sold',
  EXPIRED: 'Expired',
  DRAFT: 'Private draft',
  ANALYSING: 'Checking ad',
  FLAGGED: 'Needs review',
  RESERVED: 'Reserved',
  REMOVED: 'Removed',
  PROFILE_REQUIRED: 'Complete verification',
};
export function OwnerAds() {
  const [tab, setTab] = useState('all'),
    [input, setInput] = useState(''),
    [query, setQuery] = useState(''),
    [offset, setOffset] = useState(0),
    [notice, setNotice] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(input);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [input]);
  const { data, isPending, error } = useProfileAds(tab, query, offset);
  const qc = useQueryClient();
  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      profileRequest(`/me/profile/ads/${id}/action`, {
        method: 'POST',
        body: JSON.stringify({ action }),
      }),
    onSuccess: async () => {
      setNotice('Ad updated.');
      await qc.invalidateQueries({ queryKey: ['profile', 'ads'] });
    },
  });
  return (
    <section className="rounded-xl border border-border bg-card p-4 sm:p-5" id="my-ads">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">My ads</h2>
        <Button size="sm" asChild>
          <Link href="/dashboard/listings/new">+ Post an Ad</Link>
        </Button>
      </div>
      <div
        className="mt-4 flex gap-5 overflow-x-auto border-b border-border"
        role="tablist"
        aria-label="Your ad status"
      >
        {(['all', 'active', 'inactive'] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            aria-controls="profile-ad-results"
            onClick={() => {
              setTab(t);
              setOffset(0);
            }}
            className={`whitespace-nowrap border-b-2 px-1 pb-3 text-sm ${tab === t ? 'border-brand font-semibold text-brand' : 'border-transparent text-muted-foreground'}`}
          >
            {t === 'all' ? 'All Ads' : t === 'active' ? 'Active' : 'Inactive'} (
            {data?.counts[t] ?? '…'})
          </button>
        ))}
      </div>
      <label className="relative mt-4 block">
        <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
        <input
          aria-label="Search your ads"
          placeholder="Search your ads"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="w-full rounded-lg border border-input bg-background py-2.5 pl-9 pr-3 text-sm"
        />
      </label>
      {notice && (
        <p role="status" className="mt-3 text-sm text-brand">
          {notice}
        </p>
      )}
      {act.error && (
        <Alert tone="error" className="mt-3">
          {act.error.message}
        </Alert>
      )}
      <div id="profile-ad-results" role="tabpanel" className="mt-4">
        {isPending ? (
          <div className="py-12">
            <Spinner label="Loading your ads" />
          </div>
        ) : error ? (
          <Alert tone="error">{error.message}</Alert>
        ) : !data?.items.length ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            {query ? 'No ads match your search.' : 'No ads in this section yet.'}
          </p>
        ) : (
          <div className="grid gap-3 xl:grid-cols-2">
            {data.items.map((ad) => (
              <article
                key={ad.id}
                className="flex min-w-0 gap-3 rounded-xl border border-border p-3"
              >
                <Link
                  href={`/dashboard/listings/${ad.id}`}
                  className="relative block h-32 w-24 shrink-0 overflow-hidden rounded-lg bg-muted"
                >
                  {ad.imageUrl ? (
                    <Image
                      src={ad.imageUrl}
                      alt={ad.title}
                      fill
                      sizes="96px"
                      unoptimized
                      className="object-cover"
                    />
                  ) : (
                    <ImageOff className="m-auto mt-12 h-6 w-6 text-muted-foreground" />
                  )}
                </Link>
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/dashboard/listings/${ad.id}`}
                    className="line-clamp-2 text-sm font-semibold hover:underline"
                  >
                    {ad.title}
                  </Link>
                  <p className="mt-1 font-bold text-brand">
                    {ad.price !== null
                      ? `${ad.currency === 'PKR' ? 'Rs' : (ad.currency ?? 'Rs')} ${ad.price.toLocaleString()}`
                      : 'Price on request'}
                  </p>
                  <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3" />
                    {ad.city ?? 'Location not set'}
                  </p>
                  <span
                    className={`mt-2 inline-block rounded-full px-2 py-1 text-[11px] ${ad.isPublic ? 'bg-brand/10 text-brand' : 'bg-muted text-muted-foreground'}`}
                  >
                    {LABELS[ad.status] ?? ad.status}
                  </span>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" asChild>
                      <Link href={`/dashboard/listings/${ad.id}`}>
                        {['SOLD', 'REMOVED'].includes(ad.status) ? 'View ad' : 'Edit'}
                      </Link>
                    </Button>
                    {ad.rawStatus === 'ACTIVE' && (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={act.isPending}
                          onClick={() => {
                            if (
                              window.confirm('Mark this ad as sold? It will leave public listings.')
                            )
                              act.mutate({ id: ad.id, action: 'sold' });
                          }}
                        >
                          Mark sold
                        </Button>
                        <button
                          className="text-xs text-muted-foreground underline"
                          disabled={act.isPending}
                          onClick={() => act.mutate({ id: ad.id, action: 'pause' })}
                        >
                          Pause
                        </button>
                      </>
                    )}
                    {ad.status === 'PAUSED' && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={act.isPending}
                        onClick={() => act.mutate({ id: ad.id, action: 'resume' })}
                      >
                        Resume
                      </Button>
                    )}
                    {ad.status === 'EXPIRED' && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={act.isPending}
                        onClick={() => act.mutate({ id: ad.id, action: 'renew' })}
                      >
                        Renew
                      </Button>
                    )}
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
      {data && data.total > 12 && (
        <div className="mt-4 flex items-center justify-between">
          <Button
            size="sm"
            variant="outline"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 12))}
          >
            Previous
          </Button>
          <span className="text-xs text-muted-foreground">
            {offset + 1}–{Math.min(offset + 12, data.total)} of {data.total}
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={offset + 12 >= data.total}
            onClick={() => setOffset(offset + 12)}
          >
            Next
          </Button>
        </div>
      )}
      <p className="mt-4 rounded-lg bg-muted/40 p-3 text-xs text-muted-foreground">
        Only you can see inactive ads here. Drafts and checking ads remain private until all
        publication checks pass.
      </p>
    </section>
  );
}
