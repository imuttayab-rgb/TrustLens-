'use client';

import { useConversations } from '@/features/messaging';
import { useListingCity } from '@/features/marketplace';
import { useSession } from '@/lib/auth/use-session';
import { X } from 'lucide-react';
import { useParams, useSearchParams } from 'next/navigation';
import { useState } from 'react';
import { MessageThreadView } from '../MessageThreadView';
import { SafeMeetSidebar } from '../SafeMeetSidebar';

export default function ConversationPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const intent = searchParams.get('intent');
  const { data: session } = useSession();
  const { data: conversations } = useConversations();
  const conversation = conversations?.items.find((item) => item.id === params.id);
  const { data: listingInfo } = useListingCity(conversation?.listingId ?? null);
  const [mobileSafeMeetOpen, setMobileSafeMeetOpen] = useState(intent === 'safemeet');

  const hasSafeMeet = Boolean(conversation?.listingId) && Boolean(session?.id);

  return (
    <div className="relative flex h-full">
      <div className="min-w-0 flex-1">
        <MessageThreadView
          conversationId={params.id}
          intent={intent === 'offer' || intent === 'safemeet' ? intent : undefined}
          onOpenSafeMeet={hasSafeMeet ? () => setMobileSafeMeetOpen(true) : undefined}
        />
      </div>

      {hasSafeMeet && (
        <div className="hidden w-80 shrink-0 lg:block">
          <SafeMeetSidebar
            conversationId={params.id}
            listingCity={listingInfo?.city ?? null}
            currentUserId={session!.id}
            autoOpen={intent === 'safemeet'}
          />
        </div>
      )}

      {/* Below `lg`, SafeMeet opens as a full-screen overlay instead of a
          persistent third column - there's no room for three panes. */}
      {hasSafeMeet && mobileSafeMeetOpen && (
        <div className="absolute inset-0 z-20 bg-background lg:hidden">
          <div className="flex items-center justify-between border-b border-border p-3">
            <p className="text-sm font-bold">Plan a SafeMeet</p>
            <button
              type="button"
              onClick={() => setMobileSafeMeetOpen(false)}
              aria-label="Close"
              className="grid h-8 w-8 place-items-center rounded-full text-muted-foreground hover:bg-muted"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          <div className="h-[calc(100%-3rem)]">
            <SafeMeetSidebar
              conversationId={params.id}
              listingCity={listingInfo?.city ?? null}
              currentUserId={session!.id}
              autoOpen
            />
          </div>
        </div>
      )}
    </div>
  );
}
