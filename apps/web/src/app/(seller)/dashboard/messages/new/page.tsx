'use client';

import { useSendMessage } from '@/features/messaging';
import { Alert, Button } from '@trustlens/ui';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';

export default function NewConversationPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const listingId = searchParams.get('listingId');
  const intent = searchParams.get('intent');
  const sendMessage = useSendMessage();
  const [body, setBody] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (!listingId) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Message a seller</h1>
        <Alert tone="error" title="No listing selected" className="mt-6">
          Start a conversation from a listing on{' '}
          <Link href="/browse" className="underline underline-offset-4">
            Browse
          </Link>
          .
        </Alert>
      </div>
    );
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    setError(null);
    try {
      const result = await sendMessage.mutateAsync({
        body: trimmed,
        listingId: listingId as string,
      });
      const suffix = intent ? `?intent=${encodeURIComponent(intent)}` : '';
      router.push(`/dashboard/messages/${result.conversationId}${suffix}`);
    } catch {
      setError('Could not send that message. Try again.');
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <Link href="/browse" className="text-sm text-muted-foreground hover:underline">
        ← Back to Browse
      </Link>
      <h1 className="mt-2 text-2xl font-bold">Message the seller</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Ask about this listing before you commit to anything.
      </p>

      <form onSubmit={(event) => void handleSubmit(event)} className="mt-6 space-y-4">
        <textarea
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={5}
          placeholder="Hi, is this still available?"
          aria-label="Message"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-sm"
        />

        {error && <Alert tone="error">{error}</Alert>}

        <Button
          type="submit"
          size="lg"
          className="w-full"
          disabled={!body.trim() || sendMessage.isPending}
        >
          {sendMessage.isPending ? 'Sending…' : 'Send message'}
        </Button>
      </form>
    </div>
  );
}
