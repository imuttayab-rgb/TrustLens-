/** Profileeditform module; defines ProfileEditForm, ProfileNameForm. */
'use client';
import { useState } from 'react';
import Link from 'next/link';
import { Alert, Button, Input } from '@trustlens/ui';
import { citiesInProvince, PAKISTAN_PROVINCES, provinceOfCity } from '@trustlens/constants';
import { CityPicker } from '@/features/location';
import { type Profile, useProfileMutation } from './hooks';
export function ProfileEditForm({ profile, onClose }: { profile: Profile; onClose: () => void }) {
  const [handle, setHandle] = useState(profile.handle),
    [bio, setBio] = useState(profile.bio ?? ''),
    [city, setCity] = useState(profile.city ?? '');
  const [confirmUsername, setConfirmUsername] = useState(false);
  const [province, setProvince] = useState<string | null>(provinceOfCity(profile.city));
  const save = useProfileMutation<{
    handle: string;
    city: string;
    bio: string;
    version: number;
    confirmUsername: boolean;
  }>('/me/profile', 'PATCH');
  return (
    <form
      className="space-y-4 rounded-xl border border-brand/40 bg-card p-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(
          { handle, city, bio, version: profile.version ?? 1, confirmUsername },
          { onSuccess: onClose },
        );
      }}
    >
      <h2 className="text-lg font-semibold">
        {profile.usernameLocked ? 'Edit profile' : 'Choose your permanent username'}
      </h2>
      <label htmlFor="profile-verified-name" className="block text-sm">
        Verified name
        <Input
          id="profile-verified-name"
          value={profile.nameVerified ? profile.displayName : 'Confirm your name below'}
          disabled
          className="mt-1"
        />
      </label>
      <p className="text-xs text-muted-foreground">
        Your verified name is locked. Corrections require ID review.
      </p>
      <label htmlFor="profile-username" className="block text-sm">
        Username
        <Input
          id="profile-username"
          value={handle}
          disabled={profile.usernameLocked}
          onChange={(e) => setHandle(e.target.value)}
          minLength={3}
          maxLength={40}
          required
          className="mt-1"
          autoComplete="username"
        />
      </label>
      <p className="text-xs text-muted-foreground">
        Choose carefully. After confirmation, your username cannot be changed.
      </p>
      {!profile.usernameLocked && (
        <label className="flex gap-2 text-xs">
          <input
            type="checkbox"
            checked={confirmUsername}
            onChange={(e) => setConfirmUsername(e.target.checked)}
          />
          I understand this username is permanent and cannot be changed later.
        </label>
      )}
      <label className="block text-sm">
        Province
        <select
          value={province ?? ''}
          onChange={(e) => {
            setProvince(e.target.value || null);
            setCity('');
          }}
          className="mt-1 w-full rounded-md border border-input bg-background p-2"
        >
          <option value="">Select province / territory</option>
          {Object.keys(PAKISTAN_PROVINCES)
            .sort()
            .map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
        </select>
      </label>
      <div className="text-sm">
        City
        <CityPicker
          value={city}
          onChange={setCity}
          cities={citiesInProvince(province)}
          province={province}
        />
      </div>
      <label className="block text-sm">
        About
        <textarea
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          maxLength={1000}
          rows={3}
          className="mt-1 w-full rounded-md border border-input bg-background p-2"
        />
      </label>
      {save.error && <Alert tone="error">{save.error.message}</Alert>}
      <div className="flex gap-2">
        <Button
          type="submit"
          disabled={save.isPending || (!profile.usernameLocked && !confirmUsername)}
        >
          {save.isPending ? 'Saving…' : 'Save profile'}
        </Button>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
export function ProfileNameForm({ profile }: { profile: Profile }) {
  const [name, setName] = useState(profile.legalName ?? profile.extractedName ?? '');
  const [consent, setConsent] = useState(false);
  const [correction, setCorrection] = useState(false);
  const [note, setNote] = useState('');
  const save = useProfileMutation<{
    fullName: string;
    publicNameConsent: true;
    requestReview: boolean;
    note: string;
  }>('/me/profile/name');
  const pending = profile.nameRequestStatus === 'REVIEW';
  return (
    <section className="space-y-3 rounded-xl border border-border bg-card p-5" id="profile-name">
      <h2 className="font-semibold">
        ID-matched name{' '}
        {profile.nameVerified && <span className="text-sm text-brand">· Confirmed</span>}
      </h2>
      <p className="text-xs leading-relaxed text-muted-foreground">
        Your full legal name stays private. Only its first and last name appear publicly. A spelling
        or OCR mismatch goes to staff review.
      </p>
      {profile.identityStatus !== 'VERIFIED' ? (
        <Button asChild variant="outline">
          <Link href="/dashboard/verification/identity">Complete ID and selfie verification</Link>
        </Button>
      ) : (
        <>
          {pending ? (
            <Alert tone="info">
              Your name correction is awaiting staff review. You can return later.
            </Alert>
          ) : profile.nameVerified && !correction ? (
            <>
              <p className="text-sm">{profile.displayName}</p>
              <button
                type="button"
                className="text-sm text-brand underline"
                onClick={() => setCorrection(true)}
              >
                Request a name correction
              </button>
            </>
          ) : (
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                save.mutate({
                  fullName: name,
                  publicNameConsent: true,
                  requestReview: correction,
                  note,
                });
              }}
            >
              <label htmlFor="profile-legal-name" className="block text-sm">
                Full name as printed on your ID
                <Input
                  id="profile-legal-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  minLength={2}
                  maxLength={150}
                  className="mt-1"
                />
              </label>
              <label className="block text-xs">
                Correction note (if needed)
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={1000}
                  rows={2}
                  className="mt-1 w-full rounded-md border border-input bg-background p-2"
                />
              </label>
              <label className="flex gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                />
                I confirm this is my ID name and agree to display its first and last name publicly.
              </label>
              <Button disabled={!consent || !name.trim() || save.isPending}>
                {save.isPending
                  ? 'Submitting…'
                  : correction
                    ? 'Request staff review'
                    : 'Confirm name'}
              </Button>
            </form>
          )}
          {profile.nameRequestStatus === 'REJECTED' && (
            <Alert tone="warning">
              {profile.nameRequestNote ??
                'Please correct the name and resubmit, or verify your current ID again.'}
            </Alert>
          )}
          {save.error && <Alert tone="error">{save.error.message}</Alert>}
          {!profile.nameVerified && (
            <Link
              href="/dashboard/verification/identity"
              className="block text-xs text-brand underline"
            >
              Update your ID and verification selfie
            </Link>
          )}
        </>
      )}
    </section>
  );
}
