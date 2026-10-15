/** Publicprofile module; defines PublicProfile. */
'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import { Alert, Button, ScoreGauge, Spinner } from '@trustlens/ui';
import { Calendar, CheckCircle2, MapPin, Share2, ImageOff } from 'lucide-react';
import { usePublicListings } from '@/features/marketplace';
import { SellerReportButton } from '@/features/moderation';
import { FollowButton } from '@/features/reputation';
import { useSession } from '@/lib/auth/use-session';
import { ProfileAvatar } from './ProfileAvatar';
import { usePublicProfile } from './hooks';
function ActiveAds({ handle, owner }: { handle: string; owner: boolean }) {
  const [input, setInput] = useState(''),
    [query, setQuery] = useState(''),
    [offset, setOffset] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(input);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [input]);
  const { data, isPending, error } = usePublicListings({
    sellerHandle: handle,
    q: query || null,
    limit: 12,
    offset,
  });
  return (
    <section className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <h2 className="text-xl font-semibold">Active ads ({data?.total ?? '…'})</h2>
      <input
        aria-label="Search this profile’s ads"
        placeholder="Search this profile’s ads"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        className="mt-4 w-full rounded-lg border border-input bg-background p-3 text-sm"
      />
      {isPending ? (
        <div className="py-16">
          <Spinner label="Loading ads" />
        </div>
      ) : error ? (
        <Alert tone="error" className="mt-4">
          Could not load ads. Please refresh.
        </Alert>
      ) : !data?.items.length ? (
        <p className="py-16 text-center text-sm text-muted-foreground">
          {query ? 'No active ads match this search.' : 'No active ads at the moment.'}
        </p>
      ) : (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {data.items
            .filter((ad) => ad.status === 'ACTIVE')
            .map((ad) => (
              <article key={ad.id} className="overflow-hidden rounded-xl border border-border">
                <Link href={`/listing/${ad.id}`} className="relative block aspect-[4/3] bg-muted">
                  {ad.imageUrl ? (
                    <Image
                      src={ad.imageUrl}
                      alt={ad.title}
                      fill
                      sizes="(min-width:1024px) 380px, 50vw"
                      unoptimized
                      className="object-cover"
                    />
                  ) : (
                    <ImageOff className="absolute left-1/2 top-1/2 h-8 w-8 -translate-x-1/2 -translate-y-1/2 text-muted-foreground" />
                  )}
                </Link>
                <div className="p-3">
                  <Link
                    href={`/listing/${ad.id}`}
                    className="line-clamp-2 font-semibold hover:underline"
                  >
                    {ad.title}
                  </Link>
                  <p className="mt-1 text-xl font-bold text-brand">
                    {ad.price !== null
                      ? `${ad.currency === 'PKR' ? 'Rs' : (ad.currency ?? 'Rs')} ${ad.price.toLocaleString()}`
                      : 'Price on request'}
                  </p>
                  <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3" />
                    {ad.city ?? 'Pakistan'}
                    {ad.condition ? ` · ${ad.condition}` : ''}
                  </p>
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <Button asChild variant="outline" size="sm">
                      <Link href={`/listing/${ad.id}`}>View ad</Link>
                    </Button>
                    <Button asChild size="sm">
                      <Link
                        href={
                          owner
                            ? `/dashboard/listings/${ad.id}`
                            : `/messages/new?listingId=${ad.id}`
                        }
                      >
                        {owner ? 'Manage ad' : 'Chat about this ad'}
                      </Link>
                    </Button>
                  </div>
                </div>
              </article>
            ))}
        </div>
      )}
      {data && data.total > 12 && (
        <div className="mt-4 flex justify-between">
          <Button
            variant="outline"
            size="sm"
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 12))}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={offset + 12 >= data.total}
            onClick={() => setOffset(offset + 12)}
          >
            Next
          </Button>
        </div>
      )}
    </section>
  );
}
export function PublicProfile({ reference }: { reference: string }) {
  const { data: p, isPending, error } = usePublicProfile(reference);
  const { data: session } = useSession();
  const router = useRouter();
  const [shared, setShared] = useState('');
  useEffect(() => {
    if (p && reference !== p.handle) router.replace(p.profileUrl, { scroll: false });
  }, [p, reference, router]);
  async function share() {
    try {
      if (navigator.share)
        await navigator.share({
          title: `${p?.displayName ?? 'Profile'} on TrustLens`,
          url: window.location.href,
        });
      else {
        await navigator.clipboard.writeText(window.location.href);
        setShared('Profile link copied.');
      }
    } catch {
      setShared('Use the address bar to copy this profile link.');
    }
  }
  if (isPending)
    return (
      <div className="py-24">
        <Spinner label="Loading profile" />
      </div>
    );
  if (error || !p)
    return (
      <div className="mx-auto max-w-xl px-5 py-20">
        <Alert tone="error" title="Profile unavailable">
          This profile may be unavailable, or the server could not be reached.
        </Alert>
        <Button asChild className="mt-4">
          <Link href="/browse">Back to Browse</Link>
        </Button>
      </div>
    );
  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 pb-24 sm:px-6 sm:py-10">
      <p className="text-sm text-muted-foreground">
        <Link href="/browse" className="hover:underline">
          Browse
        </Link>{' '}
        / Public profile
      </p>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">{p.displayName}</h1>
          <p className="mt-1 text-sm text-muted-foreground">Public profile</p>
        </div>
        <Button variant="outline" onClick={() => void share()}>
          <Share2 className="mr-2 h-4 w-4" />
          Share profile
        </Button>
      </div>
      {shared && (
        <p role="status" className="text-sm text-brand">
          {shared}
        </p>
      )}
      <div className="grid items-start gap-5 lg:grid-cols-[310px_minmax(0,1fr)]">
        <aside className="rounded-xl border border-border bg-card p-5">
          <div className="flex flex-col items-center text-center">
            <ProfileAvatar src={p.photoUrl} name={p.displayName} size={188} />
            <h2 className="mt-5 text-2xl font-bold">{p.displayName}</h2>
            <p className="mt-1 break-all text-sm text-muted-foreground">@{p.handle}</p>
            {p.photoMatched ? (
              <>
                <span className="mt-4 flex items-center gap-2 rounded-full border border-brand/40 bg-brand/10 px-3 py-1.5 text-sm text-brand">
                  <CheckCircle2 className="h-4 w-4" />
                  Photo matched
                </span>
                <p className="mt-2 text-xs text-muted-foreground">Matched to verification selfie</p>
              </>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">Profile verification incomplete</p>
            )}
          </div>
          <div className="mt-5 space-y-3 text-sm">
            <p className="flex items-center gap-2">
              <MapPin className="h-4 w-4" />
              {p.city ?? 'Pakistan'}
            </p>
            <p className="flex items-center gap-2 text-muted-foreground">
              <Calendar className="h-4 w-4" />
              Member since{' '}
              {new Date(p.memberSince).toLocaleDateString('en-GB', {
                month: 'long',
                year: 'numeric',
              })}
            </p>
          </div>
          <div className="mt-5 border-t border-border pt-5">
            <h3 className="text-sm font-semibold">About</h3>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm text-muted-foreground">
              {p.bio ?? 'No introduction added yet.'}
            </p>
          </div>
          {p.sellerId && (
            <div className="mt-5 space-y-3 border-t border-border pt-4">
              <FollowButton handle={p.handle} />
              <SellerReportButton handle={p.handle} />
            </div>
          )}
        </aside>
        <div className="min-w-0 space-y-5">
          <section className="grid gap-5 rounded-xl border border-border bg-card p-5 md:grid-cols-[230px_minmax(0,1fr)]">
            <div className="flex flex-col items-center">
              <h2 className="font-semibold">Selling Trust Score</h2>
              {p.score !== null ? (
                <ScoreGauge score={p.score} riskLevel={p.riskLevel ?? 'UNKNOWN'} size="md" />
              ) : (
                <p className="py-16 text-sm text-muted-foreground">No selling score yet</p>
              )}
              {p.score !== null && (
                <Button size="sm" variant="outline" asChild>
                  <Link href={`/seller/${p.handle}/report`}>View score details</Link>
                </Button>
              )}
            </div>
            <div className="min-w-0 md:border-l md:border-border md:pl-5">
              <h2 className="font-semibold">Account verification</h2>
              <div className="mt-5 space-y-3">
                {(
                  [
                    { key: 'identity', label: 'ID-matched name' },
                    { key: 'phone', label: 'Phone' },
                    { key: 'email', label: 'Email' },
                  ] as const
                ).map((v) => (
                  <div
                    key={v.key}
                    className="flex items-center gap-3 rounded-lg border border-border p-3 text-sm"
                  >
                    <CheckCircle2
                      className={`h-5 w-5 ${p.verification[v.key] ? 'text-brand' : 'text-muted-foreground/40'}`}
                    />
                    {v.label}
                    <span className="ml-auto text-xs text-muted-foreground">
                      {p.verification[v.key] ? 'Verified' : 'Not verified'}
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-5 text-xs text-muted-foreground">
                Contact details and identity documents are kept private.
              </p>
            </div>
          </section>
          {p.sellerId ? (
            <ActiveAds handle={p.handle} owner={session?.id === p.userId} />
          ) : (
            <section className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
              No active ads at the moment.
            </section>
          )}
          <p className="text-xs leading-relaxed text-muted-foreground">
            Photo matching compares the uploaded photo with the account’s verification selfie. It
            does not establish who is currently using the account or guarantee a safe transaction.
          </p>
        </div>
      </div>
    </div>
  );
}
