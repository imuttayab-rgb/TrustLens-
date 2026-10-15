/** Next.js route/layout composition for (public)/messages: page. */
import { MessageCircle } from 'lucide-react';

export default function MessagesIndexPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
      <MessageCircle className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
      <p className="font-medium">Select a conversation</p>
      <p className="max-w-xs text-sm text-muted-foreground">
        Choose a conversation from the list to read and reply.
      </p>
    </div>
  );
}
