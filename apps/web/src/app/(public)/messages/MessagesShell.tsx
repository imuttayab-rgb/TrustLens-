'use client';

import { cn } from '@trustlens/utils';
import { usePathname } from 'next/navigation';
import { ConversationSidebar } from './ConversationSidebar';

/**
 * Owns the responsive split between the conversation list and whatever's
 * selected - on mobile only one pane shows at a time (the list at
 * `/messages`, the thread once a conversation is picked), on desktop both
 * show together. One component making that call, rather than the sidebar
 * and each page independently guessing at each other's route.
 */
export function MessagesShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hasActiveConversation = pathname !== '/messages';

  return (
    <div className="mx-auto flex h-[calc(100dvh-6rem)] min-h-[28rem] max-w-7xl overflow-hidden rounded-xl border border-border shadow-sm">
      <div className={cn('w-full shrink-0 md:w-80', hasActiveConversation && 'hidden md:block')}>
        <ConversationSidebar />
      </div>
      <div className={cn('min-w-0 flex-1', !hasActiveConversation && 'hidden md:block')}>
        {children}
      </div>
    </div>
  );
}
