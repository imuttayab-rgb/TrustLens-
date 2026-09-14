'use client';

import { ReportButton } from '@/features/moderation';
import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field, fieldAria, Input, Spinner } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { useState } from 'react';
import {
  useMeetups,
  useNearbyVenues,
  useProposeMeetup,
  useRespondToMeetup,
  type Meetup,
} from '../hooks/use-safemeet';

const STATUS_LABEL: Record<Meetup['status'], string> = {
  PROPOSED: 'Proposed',
  ACCEPTED: 'Accepted',
  DECLINED: 'Declined',
  CANCELLED: 'Cancelled',
};

function formatWhen(iso: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/**
 * SafeMeet proposals for one conversation: a platform-suggested public spot
 * plus a time, mutually accepted rather than just offered. Only useful once
 * the listing's city is known - venues are suggested per city.
 */
export function MeetupPanel({
  conversationId,
  listingCity,
  currentUserId,
  autoOpen = false,
}: {
  conversationId: string;
  listingCity: string | null;
  currentUserId: string;
  /** Opens the "propose a SafeMeet" form immediately - a buyer arriving
   * here from the listing page's "Propose a SafeMeet" button. */
  autoOpen?: boolean;
}) {
  const { data: meetups, isPending } = useMeetups(conversationId);
  const { data: venues, isPending: venuesPending } = useNearbyVenues(listingCity);
  const proposeMeetup = useProposeMeetup(conversationId);
  const respondToMeetup = useRespondToMeetup(conversationId);
  const [showForm, setShowForm] = useState(autoOpen);
  const [venueId, setVenueId] = useState('');
  const [when, setWhen] = useState('');
  const [message, setMessage] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [respondError, setRespondError] = useState<string | null>(null);

  const openMeetup = meetups?.find((m) => m.status === 'PROPOSED');
  const history = meetups?.filter((m) => m.id !== openMeetup?.id) ?? [];

  async function handleSubmit() {
    if (!venueId) {
      setFormError('Choose a meetup spot.');
      return;
    }
    if (!when) {
      setFormError('Choose a date and time.');
      return;
    }
    const iso = new Date(when).toISOString();
    setFormError(null);
    try {
      const trimmedMessage = message.trim();
      await proposeMeetup.mutateAsync(
        trimmedMessage
          ? { venueId, proposedTime: iso, message: trimmedMessage }
          : { venueId, proposedTime: iso },
      );
      setVenueId('');
      setWhen('');
      setMessage('');
      setShowForm(false);
    } catch (error) {
      setFormError(toApiError(error).message);
    }
  }

  async function handleRespond(meetupId: string, accept: boolean) {
    setRespondError(null);
    try {
      await respondToMeetup.mutateAsync({ meetupId, accept });
    } catch (error) {
      setRespondError(toApiError(error).message);
    }
  }

  if (!listingCity) return null;

  return (
    <div className="space-y-3 border-b border-border p-3">
      {isPending ? (
        <Spinner label="Loading SafeMeet proposals" />
      ) : (
        <>
          {openMeetup && (
            <MeetupRow
              meetup={openMeetup}
              venue={venues?.find((v) => v.id === openMeetup.venueId)}
              currentUserId={currentUserId}
              highlighted
              onRespond={(accept) => void handleRespond(openMeetup.id, accept)}
              responding={respondToMeetup.isPending}
            />
          )}
          {respondError && <Alert tone="error">{respondError}</Alert>}

          {history.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer text-muted-foreground">
                SafeMeet history ({history.length})
              </summary>
              <div className="mt-2 space-y-2">
                {history.map((meetup) => (
                  <MeetupRow
                    key={meetup.id}
                    meetup={meetup}
                    venue={venues?.find((v) => v.id === meetup.venueId)}
                    currentUserId={currentUserId}
                  />
                ))}
              </div>
            </details>
          )}
        </>
      )}

      {!openMeetup &&
        (showForm ? (
          <div className="space-y-2 rounded-lg border border-border p-3">
            <Field htmlFor="meetup-venue" label="Meetup spot" required>
              {venuesPending ? (
                <Spinner label="Loading suggested spots" />
              ) : !venues || venues.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No verified public spots suggested for {listingCity} yet.
                </p>
              ) : (
                <select
                  {...fieldAria('meetup-venue')}
                  value={venueId}
                  onChange={(event) => setVenueId(event.target.value)}
                  className="h-11 w-full rounded-md border border-input bg-background px-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-sm"
                >
                  <option value="">Choose a spot…</option>
                  {venues.map((venue) => (
                    <option key={venue.id} value={venue.id}>
                      {venue.name} — {venue.address}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field htmlFor="meetup-time" label="Date and time" required>
              <Input
                {...fieldAria('meetup-time')}
                type="datetime-local"
                value={when}
                onChange={(event) => setWhen(event.target.value)}
              />
            </Field>
            <Field htmlFor="meetup-message" label="Message" hint="Optional">
              <Input
                {...fieldAria('meetup-message')}
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="e.g. Does this time work for you?"
              />
            </Field>
            {formError && <Alert tone="error">{formError}</Alert>}
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={proposeMeetup.isPending}
                onClick={() => void handleSubmit()}
              >
                {proposeMeetup.isPending ? 'Sending…' : 'Propose SafeMeet'}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button size="sm" variant="outline" onClick={() => setShowForm(true)}>
            Propose a SafeMeet
          </Button>
        ))}
    </div>
  );
}

function MeetupRow({
  meetup,
  venue,
  currentUserId,
  highlighted,
  onRespond,
  responding,
}: {
  meetup: Meetup;
  venue: { name: string; address: string } | undefined;
  currentUserId: string;
  highlighted?: boolean;
  onRespond?: (accept: boolean) => void;
  responding?: boolean;
}) {
  const isMine = meetup.proposedBy === currentUserId;
  const canRespond = onRespond && meetup.status === 'PROPOSED' && !isMine;

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 rounded-lg border p-3 text-sm',
        highlighted ? 'border-brand bg-brand/5' : 'border-border',
      )}
    >
      <div>
        <p className="font-medium">{venue ? venue.name : 'Suggested spot'}</p>
        {venue && <p className="text-muted-foreground">{venue.address}</p>}
        <p className="text-muted-foreground">
          {formatWhen(meetup.proposedTime)} · {isMine ? 'You proposed' : 'They proposed'} ·{' '}
          {STATUS_LABEL[meetup.status]}
        </p>
        {meetup.message && (
          <p className="mt-1 text-muted-foreground">&ldquo;{meetup.message}&rdquo;</p>
        )}
        {meetup.status === 'ACCEPTED' && (
          <div className="mt-2">
            <ReportButton targetType="MEETUP" targetId={meetup.id} label="Report an issue" />
          </div>
        )}
      </div>
      {canRespond && (
        <div className="flex shrink-0 gap-2">
          <Button size="sm" disabled={responding} onClick={() => onRespond(true)}>
            Accept
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={responding}
            onClick={() => onRespond(false)}
          >
            Decline
          </Button>
        </div>
      )}
    </div>
  );
}
