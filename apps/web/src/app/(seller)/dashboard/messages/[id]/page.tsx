'use client';

import { MessageThread } from '@/features/messaging';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';

export default function ConversationPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const intent = searchParams.get('intent');

  return (
    <div>
      <Link href="/dashboard/messages" className="text-sm text-muted-foreground hover:underline">
        ← Back to messages
      </Link>
      <h1 className="mt-2 text-2xl font-bold">Conversation</h1>

      <div className="mt-6">
        <MessageThread
          conversationId={params.id}
          intent={intent === 'offer' || intent === 'safemeet' ? intent : undefined}
        />
      </div>
    </div>
  );
}
