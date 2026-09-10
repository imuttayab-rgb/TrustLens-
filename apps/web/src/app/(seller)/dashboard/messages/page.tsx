import { ConversationList } from '@/features/messaging';

export default function MessagesPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold">Messages</h1>
      <p className="mt-1 text-sm text-muted-foreground">Conversations with buyers and sellers.</p>

      <div className="mt-8">
        <ConversationList />
      </div>
    </div>
  );
}
