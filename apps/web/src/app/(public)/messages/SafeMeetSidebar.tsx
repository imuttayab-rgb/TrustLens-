/** Next.js route/layout composition for (public)/messages: SafeMeetSidebar. */
'use client';

import {
  useMeetups,
  useNearbyVenues,
  useProposeMeetup,
  useRespondToMeetup,
} from '@/features/safemeet';
import { Alert, Button, Spinner } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { Lock, MapPin, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

function formatWhen(iso: string) {
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
      new Date(iso),
    );
  } catch {
    return iso;
  }
}

export function SafeMeetSidebar({
  conversationId,
  listingCity,
  currentUserId,
  autoOpen = false,
}: {
  conversationId: string;
  listingCity: string | null;
  currentUserId: string;
  autoOpen?: boolean;
}) {
  const { data: meetups, isPending } = useMeetups(conversationId);
  const { data: venues, isPending: venuesPending } = useNearbyVenues(listingCity);
  const proposeMeetup = useProposeMeetup(conversationId);
  const respondToMeetup = useRespondToMeetup(conversationId);

  const [venueId, setVenueId] = useState('');
  const [when, setWhen] = useState('');
  const [message, setMessage] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [respondError, setRespondError] = useState<string | null>(null);
  const [editing, setEditing] = useState(autoOpen);

  const openMeetup = meetups?.find((m) => m.status === 'PROPOSED');
  const openVenue = openMeetup ? venues?.find((v) => v.id === openMeetup.venueId) : undefined;
  const isMine = openMeetup?.proposedBy === currentUserId;

  async function handleSend() {
    if (!venueId) {
      setFormError('Choose a meetup spot.');
      return;
    }
    if (!when) {
      setFormError('Choose a date and time.');
      return;
    }
    setFormError(null);
    try {
      const iso = new Date(when).toISOString();
      const trimmed = message.trim();
      await proposeMeetup.mutateAsync(
        trimmed ? { venueId, proposedTime: iso, message: trimmed } : { venueId, proposedTime: iso },
      );
      setVenueId('');
      setWhen('');
      setMessage('');
      setEditing(false);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Could not send that proposal.');
    }
  }

  async function handleRespond(accept: boolean) {
    if (!openMeetup) return;
    setRespondError(null);
    try {
      await respondToMeetup.mutateAsync({ meetupId: openMeetup.id, accept });
    } catch (error) {
      setRespondError(error instanceof Error ? error.message : 'Could not respond.');
    }
  }

  if (!listingCity) return null;

  return (
    <div className="flex h-full flex-col overflow-y-auto border-l border-border p-4">
      <h2 className="flex items-center gap-1.5 text-sm font-bold">
        <ShieldCheck className="h-4 w-4 text-brand" aria-hidden="true" />
        Plan a SafeMeet
      </h2>
      <p className="mt-1 text-xs text-muted-foreground">
        Meet in public, verified SafeMeet locations. Exact home addresses remain private.
      </p>

      {isPending ? (
        <div className="mt-4 flex justify-center">
          <Spinner label="Loading SafeMeet status" />
        </div>
      ) : openMeetup ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-lg border border-brand bg-brand/5 p-3 text-sm">
            <p className="font-medium">{openVenue ? openVenue.name : 'Suggested spot'}</p>
            {openVenue && <p className="text-muted-foreground">{openVenue.address}</p>}
            <p className="mt-1 text-muted-foreground">{formatWhen(openMeetup.proposedTime)}</p>
            {openMeetup.message && (
              <p className="mt-1 text-muted-foreground">&ldquo;{openMeetup.message}&rdquo;</p>
            )}
          </div>

          <div className="space-y-1.5 text-sm">
            <p className="font-medium">Status</p>
            <p className="text-muted-foreground">
              {isMine
                ? 'You proposed this meetup - waiting for a response.'
                : 'They proposed this meetup.'}
            </p>
          </div>

          {respondError && <Alert tone="error">{respondError}</Alert>}

          {!isMine && (
            <div className="flex gap-2">
              <Button
                className="flex-1"
                disabled={respondToMeetup.isPending}
                onClick={() => void handleRespond(true)}
              >
                Accept
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                disabled={respondToMeetup.isPending}
                onClick={() => void handleRespond(false)}
              >
                Decline
              </Button>
            </div>
          )}
        </div>
      ) : editing ? (
        <div className="mt-4 space-y-4">
          <div>
            <p className="mb-2 text-sm font-semibold">Recommended public locations</p>
            {venuesPending ? (
              <Spinner label="Loading suggested spots" />
            ) : !venues || venues.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No verified public spots suggested for {listingCity} yet.
              </p>
            ) : (
              <ul className="space-y-2">
                {venues.map((venue, index) => (
                  <li
                    key={venue.id}
                    className={cn(
                      'flex items-start gap-3 rounded-lg border p-3',
                      venueId === venue.id ? 'border-brand bg-brand/5' : 'border-border',
                    )}
                  >
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand text-xs font-bold text-[hsl(var(--background))]">
                      {index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{venue.name}</p>
                      <p className="truncate text-xs text-muted-foreground">{venue.address}</p>
                    </div>
                    <Button
                      size="sm"
                      variant={venueId === venue.id ? 'default' : 'outline'}
                      onClick={() => setVenueId(venue.id)}
                    >
                      {venueId === venue.id ? 'Selected' : 'Select'}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <label htmlFor="safemeet-when" className="mb-1 block text-sm font-semibold">
              Date and time
            </label>
            <input
              id="safemeet-when"
              type="datetime-local"
              value={when}
              onChange={(event) => setWhen(event.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          <div>
            <label htmlFor="safemeet-message" className="mb-1 block text-sm font-semibold">
              Message <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <input
              id="safemeet-message"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="e.g. Does this time work for you?"
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          {formError && <Alert tone="error">{formError}</Alert>}

          <Button
            className="w-full"
            disabled={proposeMeetup.isPending}
            onClick={() => void handleSend()}
          >
            {proposeMeetup.isPending ? 'Sending…' : 'Send SafeMeet Proposal'}
          </Button>
          <Button variant="outline" className="w-full" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <Button className="mt-4 w-full" onClick={() => setEditing(true)}>
          <MapPin className="h-4 w-4" aria-hidden="true" />
          Plan a SafeMeet
        </Button>
      )}

      <p className="mt-4 flex items-center gap-1.5 text-xs text-muted-foreground">
        <Lock className="h-3 w-3" aria-hidden="true" />
        Exact home addresses remain private.
      </p>
    </div>
  );
}
