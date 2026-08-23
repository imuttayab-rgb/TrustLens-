import { AuditTrail } from '@/features/audit';

export const metadata = { title: 'Audit log' };

export default function AuditLogPage() {
  return (
    <main className="mx-auto max-w-6xl p-6 sm:p-8">
      <h1 className="text-2xl font-bold">Audit log</h1>
      <p className="mt-1 text-muted-foreground">
        Every admin action recorded with actor, timestamp, and before/after state. Immutable.
      </p>
      <AuditTrail />
    </main>
  );
}
