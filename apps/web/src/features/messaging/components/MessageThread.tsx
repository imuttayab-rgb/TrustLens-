'use client';

import { useSession } from '@/lib/auth/use-session';
import { OfferPanel } from '@/features/commerce';
import { BlockButton } from '@/features/moderation';
import { Alert, Button, Spinner } from '@trustlens/ui';
import { cn } from '@trustlens/utils';
import { Send } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useConversations, useMessages, useSendMessage } from '../hooks/use-messaging';

export function MessageThread({ conversationId }: { conversationId: string }) {
  const { data: session } = useSession();
  const { data: messages, isPending, isError } = useMessages(conversationId);
  const { data: conversations } = useConversations();
  const sendMessage = useSendMessage();
  const [draft, setDraft] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const conversation = conversations?.items.find((item) => item.id === conversationId);

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
          <BlockButton
            userId={conversation.counterpartUserId}
            userName={conversation.counterpartName}
          />
        </div>
      )}
      {conversation?.listingId && session?.id && (
        <OfferPanel
          conversationId={conversationId}
          listingId={conversation.listingId}
          currentUserId={session.id}
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
            return (
              <div key={message.id} className={cn('flex', mine ? 'justify-end' : 'justify-start')}>
                <div
                  className={cn(
                    'max-w-[75%] rounded-lg px-3 py-2 text-sm',
                    mine ? 'bg-brand text-[hsl(var(--background))]' : 'bg-muted text-foreground',
                  )}
                >
                  <p className="whitespace-pre-wrap break-words">{message.body}</p>
                </div>
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
