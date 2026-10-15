/** Reusable UI rendering and interaction component: MessageThreadView. */
'use client';

import { OfferPanel } from '@/features/commerce';
import { useMessageThreadListing } from '@/features/marketplace';
import { ReportButton } from '@/features/moderation';
import { ProfileAvatar, useMyProfile } from '@/features/profile';
import { useSellerScore } from '@/features/reputation';
import { useSession } from '@/lib/auth/use-session';
import { Alert, RiskBadge, Spinner } from '@trustlens/ui';
import { cn, formatRelative } from '@trustlens/utils';
import { Bell, BellOff, IdCard, ImageOff, Mail, MapPin, Phone } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';
import { useConversation, useSetConversationMuted } from '../hooks/use-messaging';
import { ChatExperience } from './ChatExperience';

const VERIFICATION_ITEMS: { key: string; label: string; icon: typeof IdCard }[] = [
  { key: 'identity', label: 'Identity', icon: IdCard },
  { key: 'phone', label: 'Phone', icon: Phone },
  { key: 'email', label: 'Email', icon: Mail },
];

export function MessageThreadView({
  conversationId,
  intent,
  onOpenSafeMeet,
}: {
  conversationId: string;
  intent?: 'offer' | 'safemeet' | undefined;
  /** Below `lg` there's no room for a persistent SafeMeet column, so this
   * opens it as a full-screen overlay instead - omitted entirely when the
   * conversation has no listing to propose a meetup about. */
  onOpenSafeMeet?: (() => void) | undefined;
}) {
  const { data: session } = useSession();
  const {
    data: conversation,
    error: conversationError,
    refetch: refetchConversation,
  } = useConversation(conversationId);
  const setMuted = useSetConversationMuted();
  const [verificationOpen, setVerificationOpen] = useState(false);
  const [notice, setNotice] = useState('');
  const { data: ownProfile } = useMyProfile();
  const { data: listing } = useMessageThreadListing(conversation?.listingId ?? null);
  const { data: sellerScore } = useSellerScore(conversation?.counterpartSellerHandle ?? null);

  if (conversationError)
    return (
      <Alert tone="error" title="Could not load conversation">
        {conversationError.message}
        <button className="ml-2 underline" onClick={() => void refetchConversation()}>
          Retry
        </button>
      </Alert>
    );
  if (!conversation) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Loading conversation" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
        <Link
          href={conversation.counterpartProfileUrl ?? `/profile/${conversation.counterpartUserId}`}
          aria-label={`View ${conversation.counterpartName}'s profile`}
          className="flex min-w-0 items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ProfileAvatar
            src={conversation.counterpartAvatarUrl}
            name={conversation.counterpartName}
            size={44}
          />
          <div className="min-w-0">
            <p className="truncate text-sm font-bold hover:underline">
              {conversation.counterpartName}
            </p>
            <p className="text-xs text-muted-foreground">
              {conversation.counterpartPhotoMatched ? 'Photo matched · ' : ''}View profile
            </p>
          </div>
        </Link>

        <div className="flex shrink-0 items-center gap-3">
          {sellerScore && (
            <>
              <RiskBadge
                riskLevel={sellerScore.riskLevel}
                score={sellerScore.score}
                className="hidden sm:inline-flex"
              />
              <div
                className="flex items-center gap-2 border-l border-border pl-3"
                aria-label="Verification badges"
              >
                <span className="hidden text-xs text-muted-foreground lg:inline">Verification</span>
                {VERIFICATION_ITEMS.filter((item) => item.key in sellerScore.verifications).map(
                  (item) => {
                    const Icon = item.icon;
                    const done = sellerScore.verifications[item.key] === 'VERIFIED';
                    return (
                      <button
                        type="button"
                        key={item.key}
                        aria-label={`${item.label} verification: ${done ? 'verified' : 'not verified'}. Show details`}
                        aria-expanded={verificationOpen}
                        onClick={() => setVerificationOpen(!verificationOpen)}
                        title={`${item.label} ${done ? 'verified' : 'not verified'}`}
                        className={cn(
                          'grid h-8 w-8 place-items-center rounded-full focus-visible:ring-2 focus-visible:ring-ring',
                          done ? 'bg-risk-low-bg text-risk-low' : 'bg-muted text-muted-foreground',
                        )}
                      >
                        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    );
                  },
                )}
              </div>
            </>
          )}
          {onOpenSafeMeet && (
            <button
              type="button"
              onClick={onOpenSafeMeet}
              aria-label="Plan a SafeMeet"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-border text-muted-foreground transition-colors hover:bg-muted lg:hidden"
            >
              <MapPin className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
          <button
            type="button"
            aria-pressed={conversation.muted}
            disabled={setMuted.isPending}
            onClick={() => {
              setNotice('');
              setMuted.mutate(
                { conversationId, muted: !conversation.muted },
                {
                  onSuccess: (data) =>
                    setNotice(
                      data.muted
                        ? 'Message notifications muted for this chat. Calls have separate alerts.'
                        : 'Message notifications unmuted for this chat.',
                    ),
                },
              );
            }}
            className={cn(
              'grid h-9 w-9 shrink-0 place-items-center rounded-full border border-border text-muted-foreground transition-colors hover:bg-muted',
              conversation.muted && 'bg-muted text-foreground',
            )}
            aria-label={
              conversation.muted ? 'Unmute message notifications' : 'Mute message notifications'
            }
            title={
              conversation.muted
                ? 'Message notifications muted — click to unmute'
                : 'Message notifications on — click to mute'
            }
          >
            {conversation.muted ? (
              <BellOff className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Bell className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      {verificationOpen && sellerScore && (
        <div
          className="border-b border-border bg-muted/30 px-4 py-3 text-xs"
          aria-label="Verification details"
        >
          <p className="font-semibold">Verification status</p>
          <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
            {VERIFICATION_ITEMS.map((item) => (
              <li key={item.key}>
                {item.label}:{' '}
                {sellerScore.verifications[item.key] === 'VERIFIED' ? 'Verified' : 'Not verified'}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-muted-foreground">
            These badges show verification status. Use Voice call below to call inside TrustLens.
          </p>
          <button
            type="button"
            className="mt-2 underline"
            onClick={() => setVerificationOpen(false)}
          >
            Close verification details
          </button>
        </div>
      )}
      {setMuted.isError ? (
        <p role="alert" className="border-b border-border px-4 py-2 text-xs text-red-600">
          Could not change message notifications. {setMuted.error.message} Please try again.
        </p>
      ) : (
        (setMuted.isPending || notice) && (
          <p role="status" className="border-b border-border px-4 py-2 text-xs">
            {setMuted.isPending ? 'Saving notification setting…' : notice}
          </p>
        )
      )}

      {listing && (
        <div className="flex items-center gap-3 border-b border-border bg-muted/30 p-3">
          <Link
            href={`/listing/${listing.id}`}
            className="relative h-14 w-14 shrink-0 overflow-hidden rounded-md border border-border bg-muted"
          >
            {listing.images[0] ? (
              <Image
                src={listing.images[0].thumbnailUrl ?? listing.images[0].imageUrl}
                alt={listing.title}
                fill
                className="object-cover"
                unoptimized
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                <ImageOff className="h-5 w-5 opacity-40" aria-hidden="true" />
              </div>
            )}
          </Link>
          <div className="min-w-0 flex-1">
            <Link
              href={`/listing/${listing.id}`}
              className="truncate text-sm font-semibold hover:underline"
            >
              {listing.title}
            </Link>
            <p className="text-sm font-bold text-brand">
              {listing.price !== null
                ? `${listing.currency ?? ''} ${listing.price.toLocaleString()}`
                : 'Price on request'}
            </p>
            <p className="text-xs text-muted-foreground">
              Listed {formatRelative(listing.createdAt)}
            </p>
          </div>
          <ReportButton targetType="LISTING" targetId={listing.id} label="Report" />
        </div>
      )}

      {conversation.listingId && session?.id && conversation.canSend !== false && (
        <OfferPanel
          conversationId={conversationId}
          listingId={conversation.listingId}
          currentUserId={session.id}
          autoOpen={intent === 'offer'}
        />
      )}

      <ChatExperience
        key={conversationId}
        conversation={conversation}
        userId={session?.id ?? ''}
        profileReady={Boolean(ownProfile?.canInteract)}
      />
    </div>
  );
}
