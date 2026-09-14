'use client';

import { useSession } from '@/lib/auth/use-session';
import { OfferPanel } from '@/features/commerce';
import { useListingCity } from '@/features/marketplace';
import { BlockButton } from '@/features/moderation';
import { MeetupPanel } from '@/features/safemeet';
import { Alert, Button, Spinner } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { BellOff, Send, TriangleAlert } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import {
  useConversations,
  useMessages,
  useSendMessage,
  useSetConversationMuted,
} from '../hooks/use-messaging';
import { assessMessageRisk, hasRiskFlags } from '../lib/risk-heuristics';

export function MessageThread({
  conversationId,
  intent,
}: {
  conversationId: string;
  /** Auto-opens the matching panel's form - set when the buyer arrived here
   * via the listing page's "Make an offer"/"Propose a SafeMeet" buttons,
   * not by opening an existing conversation from the inbox. */
  intent?: 'offer' | 'safemeet' | undefined;
}) {
  const { data: session } = useSession();
  const { data: messages, isPending, isError } = useMessages(conversationId);
  const { data: conversations } = useConversations();
  const sendMessage = useSendMessage();
  const setMuted = useSetConversationMuted();
  const [draft, setDraft] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const conversation = conversations?.items.find((item) => item.id === conversationId);
  const { data: listingInfo } = useListingCity(conversation?.listingId ?? null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' });
  }, [messages?.length]);

  async function handleSend() {
    const body = draft.trim();
    if (!body) return;
    setDraft('');
    await sendMessage.mutateAsync({ body, conversationId });
  }

  return (
    <div className="flex h-[65dvh] flex-col rounded-lg border border-border">
      {conversation && (
        <div className="flex items-center justify-between gap-2 border-b border-border p-3">
          <p className="truncate text-sm font-medium">{conversation.counterpartName}</p>
          <div className="flex shrink-0 items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={setMuted.isPending}
              aria-pressed={conversation.muted}
              onClick={() => setMuted.mutate({ conversationId, muted: !conversation.muted })}
            >
              <BellOff className="h-4 w-4" aria-hidden="true" />
              {conversation.muted ? 'Unmute' : 'Mute'}
            </Button>
            <BlockButton
              userId={conversation.counterpartUserId}
              userName={conversation.counterpartName}
            />
          </div>
        </div>
      )}
      {conversation?.listingId && session?.id && (
        <OfferPanel
          conversationId={conversationId}
          listingId={conversation.listingId}
          currentUserId={session.id}
          autoOpen={intent === 'offer'}
        />
      )}
      {conversation?.listingId && session?.id && (
        <MeetupPanel
          conversationId={conversationId}
          listingCity={listingInfo?.city ?? null}
          currentUserId={session.id}
          autoOpen={intent === 'safemeet'}
        />
      )}
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {isPending ? (
          <div className="flex h-full items-center justify-center">
            <Spinner label="Loading messages" />
          </div>
        ) : isError ? (
          <Alert tone="error" title="Could not load this conversation">
            Try again in a moment.
          </Alert>
        ) : messages.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No messages yet - say hello.
          </p>
        ) : (
          messages.map((message) => {
            const mine = message.senderId === session?.id;
            const risk = assessMessageRisk(message.body);
            return (
              <div
                key={message.id}
                className={cn('flex flex-col', mine ? 'items-end' : 'items-start')}
              >
                <div
                  className={cn(
                    'max-w-[75%] rounded-lg px-3 py-2 text-sm',
                    mine ? 'bg-brand text-[hsl(var(--background))]' : 'bg-muted text-foreground',
                  )}
                >
                  <p className="whitespace-pre-wrap break-words">{message.body}</p>
                </div>
                {!mine && hasRiskFlags(risk) && (
                  <p className="mt-1 flex max-w-[75%] items-start gap-1 text-xs text-amber-600">
                    <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    {risk.paymentPressure
                      ? "Be cautious - never pay in advance for something you haven't seen. Use SafeMeet and pay in person."
                      : 'Be cautious with links from people you just met - verify before clicking.'}
                  </p>
                )}
              </div>
            );
          })
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
          rows={2}
          placeholder="Write a message…"
          aria-label="Message"
          className="flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button
          type="submit"
          size="icon"
          disabled={!draft.trim() || sendMessage.isPending}
          aria-label="Send message"
        >
          <Send className="h-4 w-4" aria-hidden="true" />
        </Button>
      </form>
    </div>
  );
}
