import { RequireSession } from '@/features/auth';
import { MessagesShell } from './MessagesShell';

export default function MessagesLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireSession>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <MessagesShell>{children}</MessagesShell>
      </main>
    </RequireSession>
  );
}
