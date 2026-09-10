'use client';

import { Alert, Spinner } from '@trustlens/ui';
import { formatRelative } from '@trustlens/utils';
import { MessageCircle } from 'lucide-react';
import Link from 'next/link';
import { useConversations } from '../hooks/use-messaging';

export function ConversationList() {
  const { data, isPending, isError } = useConversations();

  if (isPending) {
    return (
      <div className="flex justify-center py-16">
        <Spinner label="Loading your messages" />
      </div>
    );
  }

  if (isError) {
    return (
      <Alert tone="error" title="Could not load your messages">
        Try again in a moment.
      </Alert>
    );
  }

  if (data.items.length === 0) {
    return (
      <Alert tone="info" title="No conversations yet">
        Message a seller from a listing on Browse to start one.
      </Alert>
    );
  }

  return (
    <ul className="divide-y divide-border rounded-lg border border-border">
      {data.items.map((conversation) => (
        <li key={conversation.id}>
          <Link
            href={`/dashboard/messages/${conversation.id}`}
            className="flex items-start gap-3 p-4 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
          >
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-muted text-muted-foreground">
              <MessageCircle className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="truncate font-medium">{conversation.counterpartName}</p>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatRelative(conversation.lastMessageAt)}
                </span>
              </div>
              {conversation.listingTitle && (
                <p className="truncate text-xs text-muted-foreground">
                  About: {conversation.listingTitle}
                </p>
              )}
              {conversation.lastMessagePreview && (
                <p className="mt-0.5 truncate text-sm text-muted-foreground">
                  {conversation.lastMessagePreview}
                </p>
              )}
            </div>
            {conversation.unreadCount > 0 && (
              <span className="grid h-5 min-w-5 shrink-0 place-items-center rounded-full bg-brand px-1.5 text-xs font-semibold text-[hsl(var(--background))]">
                {conversation.unreadCount}
              </span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  );
}
