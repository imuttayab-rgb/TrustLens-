'use client';

import { toApiError } from '@trustlens/api-client';
import { Alert, Button } from '@trustlens/ui';
import { UserX } from 'lucide-react';
import { useState } from 'react';
import { useBlockUser } from '../hooks/use-moderation';

/**
 * Block the other party in a conversation. Deliberately no "are you sure"
 * dialog beyond the two-click confirm pattern below - blocking is reversible
 * from account settings, and a report already exists for anything that
 * needs staff attention.
 */
export function BlockButton({ userId, userName }: { userId: string; userName: string }) {
  const [confirming, setConfirming] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [blocked, setBlocked] = useState(false);
  const blockUser = useBlockUser();

  if (blocked) {
    return (
      <Alert tone="info" className="text-sm">
        You&apos;ve blocked {userName}. They can no longer message you.
      </Alert>
    );
  }

  if (confirming) {
    return (
      <div className="space-y-2 rounded-lg border border-border p-3 text-sm">
        <p>Block {userName}? They won&apos;t be able to message you again.</p>
        {failure && <Alert tone="error">{failure}</Alert>}
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="destructive"
            disabled={blockUser.isPending}
            onClick={() => {
              setFailure(null);
              blockUser.mutate(userId, {
                onSuccess: () => setBlocked(true),
                onError: (error) => setFailure(toApiError(error).message),
              });
            }}
          >
            {blockUser.isPending ? 'Blocking…' : 'Block'}
          </Button>
          <Button size="sm" variant="outline" onClick={() => setConfirming(false)}>
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <Button variant="outline" size="sm" onClick={() => setConfirming(true)}>
      <UserX className="h-4 w-4" aria-hidden="true" />
      Block
    </Button>
  );
}
