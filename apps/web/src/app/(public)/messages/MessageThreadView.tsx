'use client';

import { useSession } from '@/lib/auth/use-session';
import { OfferPanel } from '@/features/commerce';
import {
  assessMessageRisk,
  hasRiskFlags,
  useConversations,
  useMessages,
  useSendMessage,
  useSetConversationMuted,
} from '@/features/messaging';
import { useMessageThreadListing } from '@/features/marketplace';
import { ReportButton } from '@/features/moderation';
import { useSellerScore } from '@/features/reputation';
import { RiskBadge, Spinner } from '@trustlens/ui';
import { cn, formatRelative } from '@trustlens/utils';
import {
  BellOff,
  Check,
  CheckCheck,
  IdCard,
  ImageOff,
  Mail,
  MapPin,
  Phone,
  Send,
  ShieldAlert,
} from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

const VERIFICATION_ITEMS: { key: string; label: string; icon: typeof IdCard }[] = [
  { key: 'identity', label: 'Identity', icon: IdCard },
  { key: 'phone', label: 'Phone', icon: Phone },
  { key: 'email', label: 'Email', icon: Mail },
];

function dayLabel(date: Date, now: Date): string {
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
  if (sameDay(date, now)) return 'Today';
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(date, yesterday)) return 'Yesterday';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'long' }).format(date);
}

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
  const { data: messages, isPending, isError } = useMessages(conversationId);
  const { data: conversations } = useConversations();
  const sendMessage = useSendMessage();
  const setMuted = useSetConversationMuted();
  const [draft, setDraft] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const conversation = conversations?.items.find((item) => item.id === conversationId);
  const { data: listing } = useMessageThreadListing(conversation?.listingId ?? null);
  const { data: sellerScore } = useSellerScore(conversation?.counterpartSellerHandle ?? null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' });
  }, [messages?.length]);

  async function handleSend() {
    const body = draft.trim();
    if (!body) return;
    setDraft('');
    await sendMessage.mutateAsync({ body, conversationId });
  }

  if (!conversation) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Loading conversation" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-border p-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand/10 text-sm font-bold text-brand">
            {conversation.counterpartName.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold">{conversation.counterpartName}</p>
            <p className="truncate text-xs text-muted-foreground">
              {conversation.counterpartSellerHandle && `@${conversation.counterpartSellerHandle}`}
              {sellerScore?.memberSince &&
                ` · Member since ${new Date(sellerScore.memberSince).getFullYear()}`}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {sellerScore && (
            <>
              <RiskBadge
                riskLevel={sellerScore.riskLevel}
                score={sellerScore.score}
                className="hidden sm:inline-flex"
              />
              <div className="hidden items-center gap-2 border-l border-border pl-3 md:flex">
                {VERIFICATION_ITEMS.filter((item) => item.key in sellerScore.verifications).map(
                  (item) => {
                    const Icon = item.icon;
                    const done = sellerScore.verifications[item.key] === 'VERIFIED';
                    return (
                      <span
                        key={item.key}
                        title={`${item.label} ${done ? 'verified' : 'not verified'}`}
                        className={cn(
                          'grid h-6 w-6 place-items-center rounded-full',
                          done ? 'bg-risk-low-bg text-risk-low' : 'bg-muted text-muted-foreground',
                        )}
                      >
                        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                      </span>
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
            onClick={() => setMuted.mutate({ conversationId, muted: !conversation.muted })}
            className={cn(
              'grid h-9 w-9 shrink-0 place-items-center rounded-full border border-border text-muted-foreground transition-colors hover:bg-muted',
              conversation.muted && 'bg-muted text-foreground',
            )}
            aria-label={conversation.muted ? 'Unmute conversation' : 'Mute conversation'}
          >
            <BellOff className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

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

      {conversation.listingId && session?.id && (
        <OfferPanel
          conversationId={conversationId}
          listingId={conversation.listingId}
          currentUserId={session.id}
          autoOpen={intent === 'offer'}
        />
      )}

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {isPending ? (
          <div className="flex h-full items-center justify-center">
            <Spinner label="Loading messages" />
          </div>
        ) : isError ? (
          <p className="py-8 text-center text-sm text-destructive">
            Could not load this conversation.
          </p>
        ) : messages.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No messages yet - say hello.
          </p>
        ) : (
          (() => {
            const now = new Date();
            let lastLabel: string | null = null;
            return messages.map((message) => {
              const mine = message.senderId === session?.id;
              const risk = assessMessageRisk(message.body);
              const created = new Date(message.createdAt);
              const label = dayLabel(created, now);
              const showDivider = label !== lastLabel;
              lastLabel = label;
              return (
                <div key={message.id}>
                  {showDivider && (
                    <div className="my-3 flex items-center gap-3">
                      <span className="h-px flex-1 bg-border" />
                      <span className="text-xs text-muted-foreground">{label}</span>
                      <span className="h-px flex-1 bg-border" />
                    </div>
                  )}
                  <div className={cn('flex flex-col', mine ? 'items-end' : 'items-start')}>
                    <div
                      className={cn(
                        'max-w-[75%] rounded-lg px-3 py-2 text-sm',
                        mine
                          ? 'bg-brand text-[hsl(var(--background))]'
                          : 'bg-muted text-foreground',
                      )}
                    >
                      <p className="whitespace-pre-wrap break-words">{message.body}</p>
                    </div>
                    <div className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
                      {formatRelative(message.createdAt)}
                      {mine &&
                        (message.readAt ? (
                          <CheckCheck className="h-3 w-3 text-brand" aria-hidden="true" />
                        ) : (
                          <Check className="h-3 w-3" aria-hidden="true" />
                        ))}
                    </div>
                    {!mine && hasRiskFlags(risk) && (
                      <div className="mt-1.5 flex max-w-[75%] items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
                        <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                        <div>
                          <p className="font-semibold">TrustLens Safety</p>
                          <p className="mt-0.5">
                            {risk.paymentPressure
                              ? 'Keep payment and personal information inside TrustLens. Never pay in advance for something you haven’t seen.'
                              : 'Be cautious with links from people you just met - verify before clicking.'}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            });
          })()
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void handleSend();
        }}
        className="flex items-end gap-2 border-t border-border p-3"
      >
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              void handleSend();
            }
          }}
          rows={1}
          placeholder="Type a message…"
          aria-label="Message"
          className="max-h-32 flex-1 resize-none rounded-md border border-input bg-background px-3 py-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <button
          type="submit"
          disabled={!draft.trim() || sendMessage.isPending}
          aria-label="Send message"
          className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-brand text-[hsl(var(--background))] transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          <Send className="h-4 w-4" aria-hidden="true" />
        </button>
      </form>
      <p className="border-t border-border/60 px-3 py-2 text-center text-[11px] text-muted-foreground">
        Never share payment details, IDs or OTPs outside TrustLens.
      </p>
    </div>
  );
}
