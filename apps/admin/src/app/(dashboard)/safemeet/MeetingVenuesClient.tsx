/** Next.js route/layout composition for (dashboard)/safemeet: MeetingVenuesClient. */
'use client';

import {
  useCreateMeetingVenue,
  useMeetingVenues,
  useSetVenueActive,
  type AdminMeetingVenue,
} from '@/features/safemeet';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Card, CardContent, Field, fieldAria, Input, Spinner } from '@trustlens/ui';
import { useState } from 'react';

export function MeetingVenuesClient() {
  const { data: venues, isPending, error } = useMeetingVenues();
  const [showForm, setShowForm] = useState(false);

  if (isPending) {
    return (
      <div className="flex justify-center p-12">
        <Spinner label="Loading venues" />
      </div>
    );
  }
  if (error) {
    return (
      <main className="p-8">
        <Alert tone="error">Unable to load the SafeMeet venue catalogue.</Alert>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">SafeMeet venues</h1>
          <p className="mt-1 text-muted-foreground">
            The public, staff-verified spots buyers and sellers are offered for a handover - never a
            party&apos;s home address. Deactivating a venue stops it being suggested; past meetups
            keep their record of it.
          </p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>{showForm ? 'Close' : 'Add venue'}</Button>
      </div>

      {showForm && <CreateVenueForm onDone={() => setShowForm(false)} />}

      {venues.length === 0 ? (
        <Alert tone="info">No venues added yet.</Alert>
      ) : (
        <div className="space-y-3">
          {venues.map((venue) => (
            <VenueRow key={venue.id} venue={venue} />
          ))}
        </div>
      )}
    </main>
  );
}

function CreateVenueForm({ onDone }: { onDone: () => void }) {
  const create = useCreateMeetingVenue();
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [area, setArea] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    const lat = Number(latitude);
    const lng = Number(longitude);
    if (!name.trim() || !address.trim() || !city.trim()) {
      setError('Name, address and city are required.');
      return;
    }
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      setError('Latitude and longitude must be numbers.');
      return;
    }
    setError(null);
    try {
      const trimmedArea = area.trim();
      const trimmedNotes = notes.trim();
      await create.mutateAsync({
        name: name.trim(),
        address: address.trim(),
        city: city.trim(),
        latitude: lat,
        longitude: lng,
        ...(trimmedArea ? { area: trimmedArea } : {}),
        ...(trimmedNotes ? { notes: trimmedNotes } : {}),
      });
      onDone();
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3 pt-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field htmlFor="venue-name" label="Name" required>
            <Input
              {...fieldAria('venue-name')}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field htmlFor="venue-city" label="City" required>
            <Input
              {...fieldAria('venue-city')}
              value={city}
              onChange={(e) => setCity(e.target.value)}
            />
          </Field>
          <Field htmlFor="venue-address" label="Address" required className="sm:col-span-2">
            <Input
              {...fieldAria('venue-address')}
              value={address}
              onChange={(e) => setAddress(e.target.value)}
            />
          </Field>
          <Field htmlFor="venue-area" label="Area" hint="Optional">
            <Input
              {...fieldAria('venue-area')}
              value={area}
              onChange={(e) => setArea(e.target.value)}
            />
          </Field>
          <Field htmlFor="venue-lat" label="Latitude" required>
            <Input
              {...fieldAria('venue-lat')}
              type="number"
              step="0.000001"
              value={latitude}
              onChange={(e) => setLatitude(e.target.value)}
            />
          </Field>
          <Field htmlFor="venue-lng" label="Longitude" required>
            <Input
              {...fieldAria('venue-lng')}
              type="number"
              step="0.000001"
              value={longitude}
              onChange={(e) => setLongitude(e.target.value)}
            />
          </Field>
          <Field
            htmlFor="venue-notes"
            label="Notes"
            hint="Optional, e.g. hours or safety notes"
            className="sm:col-span-2"
          >
            <Input
              {...fieldAria('venue-notes')}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </Field>
        </div>
        {error && <Alert tone="error">{error}</Alert>}
        <div className="flex gap-2">
          <Button size="sm" disabled={create.isPending} onClick={() => void handleSubmit()}>
            {create.isPending ? 'Adding…' : 'Add venue'}
          </Button>
          <Button size="sm" variant="outline" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function VenueRow({ venue }: { venue: AdminMeetingVenue }) {
  const setActive = useSetVenueActive();
  const [failure, setFailure] = useState<string | null>(null);

  async function toggle() {
    setFailure(null);
    try {
      await setActive.mutateAsync({ venueId: venue.id, isActive: !venue.isActive });
    } catch (err) {
      setFailure(toApiError(err).message);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-2 pt-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="font-medium">{venue.name}</p>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {venue.address} · {venue.area ? `${venue.area}, ` : ''}
              {venue.city}
            </p>
          </div>
          <span
            className={
              venue.isActive
                ? 'rounded-full bg-risk-low-bg px-2 py-0.5 text-xs font-medium text-risk-low'
                : 'rounded-full bg-risk-unknown-bg px-2 py-0.5 text-xs font-medium text-risk-unknown'
            }
          >
            {venue.isActive ? 'Active' : 'Inactive'}
          </span>
        </div>
        {venue.notes && <p className="text-sm text-muted-foreground">{venue.notes}</p>}
        {failure && <Alert tone="error">{failure}</Alert>}
        <Button
          size="sm"
          variant="outline"
          disabled={setActive.isPending}
          onClick={() => void toggle()}
        >
          {venue.isActive ? 'Deactivate' : 'Reactivate'}
        </Button>
      </CardContent>
    </Card>
  );
}
