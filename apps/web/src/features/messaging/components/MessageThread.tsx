/** Reusable UI rendering and interaction component: MessageThread. */
'use client';
import { useListingCity } from '@/features/marketplace';
import { BlockButton } from '@/features/moderation';
import { MeetupPanel } from '@/features/safemeet';
import { useSession } from '@/lib/auth/use-session';
import { useState } from 'react';
import { useConversation } from '../hooks/use-messaging';
import { MessageThreadView } from './MessageThreadView';
export function MessageThread({
  conversationId,
  intent,
}: {
  conversationId: string;
  intent?: 'offer' | 'safemeet' | undefined;
}) {
  const { data: conversation } = useConversation(conversationId);
  const { data: session } = useSession();
  const { data: listing } = useListingCity(conversation?.listingId ?? null);
  const [meet, setMeet] = useState(intent === 'safemeet');
  return (
    <div className="flex h-[75dvh] flex-col rounded-lg border border-border">
      {conversation && (
        <div className="flex items-center justify-end border-b border-border p-2">
          <BlockButton
            userId={conversation.counterpartUserId}
            userName={conversation.counterpartName}
          />
        </div>
      )}
      {meet && conversation?.listingId && session?.id && conversation.canSend !== false && (
        <MeetupPanel
          conversationId={conversationId}
          listingCity={listing?.city ?? null}
          currentUserId={session.id}
          autoOpen
        />
      )}
      <div className="min-h-0 flex-1">
        <MessageThreadView
          conversationId={conversationId}
          intent={intent}
          onOpenSafeMeet={() => setMeet((value) => !value)}
        />
      </div>
    </div>
  );
}
