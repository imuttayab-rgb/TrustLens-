/** Ownerprofile module; defines OwnerProfile. */
'use client';
import { useState } from 'react';
import Link from 'next/link';
import { Alert, Button, ScoreGauge, Spinner, VerificationChecklist } from '@trustlens/ui';
import { Calendar, CheckCircle2, ExternalLink, LockKeyhole, MapPin, Pencil } from 'lucide-react';
import { useVerificationStatus } from '@/features/seller';
import { useMyProfile } from './hooks';
import { ProfileAvatar } from './ProfileAvatar';
import { ProfileEditForm, ProfileNameForm } from './ProfileEditForm';
import { ProfilePhotoEditor } from './ProfilePhotoEditor';
import { OwnerAds } from './OwnerAds';
export function OwnerProfile() {
  const { data: p, isPending, error, refetch } = useMyProfile();
  const { data: verification } = useVerificationStatus();
  const [editing, setEditing] = useState(false),
    [setup, setSetup] = useState(false);
  if (isPending)
    return (
      <div className="py-20">
        <Spinner label="Loading your profile" />
      </div>
    );
  if (error || !p)
    return (
      <Alert tone="error" title="Could not load your profile">
        {error?.message}
        <Button variant="outline" onClick={() => void refetch()}>
          Retry
        </Button>
      </Alert>
    );
  const showSetup = !p.canInteract || setup;
  const maskEmail = (p.email ?? '').replace(/^(.{1,2}).*(@.*)$/, '$1•••$2');
  const maskPhone = p.phone ? `${p.phone.slice(0, 3)} ••• ••• ${p.phone.slice(-2)}` : 'Not added';
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">My profile</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Your profile, verification and ads in one place.
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link href={p.profileUrl}>
            <ExternalLink className="mr-2 h-4 w-4" />
            View public profile
          </Link>
        </Button>
      </div>
      <div className="grid items-start gap-5 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[330px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <section className="rounded-xl border border-border bg-card p-5">
            <h2 className="font-semibold">Profile details</h2>
            <div className="my-5 flex flex-col items-center text-center">
              <ProfileAvatar src={p.photoUrl} name={p.displayName} size={152} />
              <button className="mt-3 text-sm text-brand underline" onClick={() => setSetup(true)}>
                Change profile photo
              </button>
              <h2 className="mt-4 text-2xl font-bold">
                {p.nameVerified ? p.displayName : 'Confirm your name'}
              </h2>
              <p className="mt-1 break-all text-sm text-muted-foreground">@{p.handle}</p>
              {p.photoMatched && (
                <span className="mt-3 flex items-center gap-1 rounded-full bg-brand/10 px-3 py-1 text-xs text-brand">
                  <CheckCircle2 className="h-3 w-3" />
                  Photo matched
                </span>
              )}
            </div>
            <div className="space-y-3 border-t border-border pt-4 text-sm">
              <p className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-muted-foreground" />
                {p.city ?? 'Add your city'}, Pakistan
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
            <h3 className="mt-5 text-sm font-semibold">About</h3>
            <p className="mt-1 whitespace-pre-wrap break-words text-sm text-muted-foreground">
              {p.bio ?? 'Add a short introduction to your profile.'}
            </p>
            <Button className="mt-5 w-full" onClick={() => setEditing((v) => !v)}>
              <Pencil className="mr-2 h-4 w-4" />
              Edit profile
            </Button>
          </section>
          <section className="space-y-3 rounded-xl border border-border bg-card p-5">
            <h2 className="font-semibold">Private contact details</h2>
            <p className="break-all text-sm text-muted-foreground">
              {maskEmail} {p.verification.email && <span className="text-brand">· Verified</span>}
            </p>
            <p className="text-sm text-muted-foreground">
              {maskPhone} {p.verification.phone && <span className="text-brand">· Verified</span>}
            </p>
            <p className="flex gap-2 border-t border-border pt-3 text-xs text-muted-foreground">
              <LockKeyhole className="h-4 w-4" />
              Visible only to you
            </p>
            <Link href="/dashboard/settings" className="block text-xs text-brand hover:underline">
              Account and security settings
            </Link>
          </section>
        </aside>
        <div className="min-w-0 space-y-5">
          <section className="grid gap-5 rounded-xl border border-border bg-card p-5 md:grid-cols-[230px_minmax(0,1fr)]">
            <div className="flex flex-col items-center">
              <h2 className="font-semibold">Selling Trust Score</h2>
              {p.score !== null ? (
                <ScoreGauge score={p.score} riskLevel={p.riskLevel ?? 'UNKNOWN'} size="md" />
              ) : (
                <p className="py-12 text-sm text-muted-foreground">No selling score yet</p>
              )}
              <Button size="sm" variant="outline" asChild>
                <Link href="/dashboard/trust-score">View score breakdown</Link>
              </Button>
            </div>
            <div className="min-w-0 md:border-l md:border-border md:pl-5">
              <h2 className="mb-4 font-semibold">Verification status</h2>
              {verification ? (
                <VerificationChecklist items={verification.checklist} actionLink={Link} />
              ) : (
                <Link href="/dashboard/verification" className="text-sm text-brand underline">
                  Open verification
                </Link>
              )}
              <p className="mt-3 text-xs text-muted-foreground">
                The selling score is separate from your required name and profile photo checks.
              </p>
            </div>
          </section>
          {!p.canInteract && (
            <Alert tone="warning" title="Complete your profile to participate">
              Choose your permanent username, confirm your ID-matched name and add an approved face
              photo before ads become public or you send messages. You can browse and prepare drafts
              now.
            </Alert>
          )}
          {(editing || !p.usernameLocked) && (
            <ProfileEditForm key={p.version} profile={p} onClose={() => setEditing(false)} />
          )}
          {(showSetup || editing) && (
            <div className="grid items-start gap-4 xl:grid-cols-2">
              <ProfileNameForm key={`${p.nameVerified}-${p.nameRequestStatus}`} profile={p} />
              <ProfilePhotoEditor
                enabled={p.nameVerified}
                status={p.photoStatus ?? 'NOT_STARTED'}
                reason={p.photoReason ?? null}
              />
            </div>
          )}
          {setup && p.canInteract && (
            <button className="text-sm text-brand underline" onClick={() => setSetup(false)}>
              Close profile checks
            </button>
          )}
          <OwnerAds />
        </div>
      </div>
    </div>
  );
}
