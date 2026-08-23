'use client';

import { useAuditLogs, type AuditLogParams } from '@/features/audit';
import { Alert, Card, CardContent, Input, Spinner } from '@trustlens/ui';
import { useState } from 'react';

const KNOWN_ENTITY_TYPES = [
  '',
  'identity_verifications',
  'scoring_models',
  'review_cases',
  'appeals',
  'api_keys',
  'sellers',
] as const;

const KNOWN_ACTIONS = [
  '',
  'identity.evidence_viewed',
  'scoring_model.activated',
  'review_case.claimed',
  'review_case.decided',
  'appeal.submitted',
  'appeal.resolved',
  'api_key.created',
  'api_key.revoked',
] as const;

function formatJson(value: Record<string, unknown> | null): string {
  if (!value || Object.keys(value).length === 0) return '—';
  return JSON.stringify(value, null, 2);
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60_000);
  const h = Math.floor(diff / 3_600_000);
  const d = Math.floor(diff / 86_400_000);
  if (m < 2) return 'just now';
  if (m < 60) return `${m}m ago`;
  if (h < 24) return `${h}h ago`;
  return `${d}d ago`;
}

export function AuditTrail() {
  const [filters, setFilters] = useState<AuditLogParams>({
    action: '',
    entityType: '',
    limit: 100,
  });
  const [expanded, setExpanded] = useState<string | null>(null);

  const params: AuditLogParams = {
    ...(filters.action ? { action: filters.action } : {}),
    ...(filters.entityType ? { entityType: filters.entityType } : {}),
    ...(filters.limit !== undefined ? { limit: filters.limit } : {}),
  };
  const { data, error, isPending, isFetching } = useAuditLogs(params);
  const entries = data?.data ?? [];

  return (
    <section className="mt-6 space-y-4">
      {/* Filters */}
      <div className="grid gap-3 rounded-lg border border-border/70 bg-card/50 p-4 md:grid-cols-[1fr_auto_auto_auto]">
        <Input
          value={filters.action ?? ''}
          onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value }))}
          placeholder="Filter by action (e.g. scoring_model.activated)"
          aria-label="Filter by action"
        />
        <select
          value={filters.entityType ?? ''}
          onChange={(e) => setFilters((f) => ({ ...f, entityType: e.target.value }))}
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          aria-label="Filter by entity type"
        >
          {KNOWN_ENTITY_TYPES.map((t) => (
            <option key={t} value={t}>
              {t === '' ? 'All entity types' : t.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
        <select
          value={String(filters.action ?? '')}
          onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value }))}
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          aria-label="Quick-select action"
        >
          {KNOWN_ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a === '' ? 'All actions' : a}
            </option>
          ))}
        </select>
        <select
          value={String(filters.limit ?? 100)}
          onChange={(e) => setFilters((f) => ({ ...f, limit: Number(e.target.value) }))}
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          aria-label="Result limit"
        >
          {[50, 100, 250, 500].map((n) => (
            <option key={n} value={n}>
              Last {n}
            </option>
          ))}
        </select>
      </div>

      {error && <Alert tone="error">Unable to load audit logs. Please try again.</Alert>}

      {isPending ? (
        <div className="flex justify-center py-12">
          <Spinner label="Loading audit log" />
        </div>
      ) : entries.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No audit log entries match these filters.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <table
              className={`w-full min-w-[820px] text-left text-sm${isFetching ? 'opacity-60' : ''}`}
            >
              <thead className="border-b border-border/70 bg-muted/30 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">When</th>
                  <th className="px-4 py-3 font-medium">Action</th>
                  <th className="px-4 py-3 font-medium">Entity</th>
                  <th className="px-4 py-3 font-medium">Actor</th>
                  <th className="px-4 py-3 font-medium">IP</th>
                  <th className="w-8 px-4 py-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <>
                    <tr
                      key={entry.id}
                      className="cursor-pointer border-b border-border/50 last:border-0 hover:bg-muted/20"
                      onClick={() => setExpanded((prev) => (prev === entry.id ? null : entry.id))}
                    >
                      <td className="whitespace-nowrap px-4 py-3 tabular-nums text-muted-foreground">
                        <span title={new Date(entry.occurredAt).toLocaleString()}>
                          {relativeTime(entry.occurredAt)}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">
                        <span className="rounded bg-muted/60 px-1.5 py-0.5">{entry.action}</span>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        <span>{entry.entityType.replace(/_/g, ' ')}</span>
                        {entry.entityId && (
                          <span className="ml-1 font-mono opacity-60">
                            {entry.entityId.slice(0, 8)}…
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        {entry.actorId ? (
                          <span className="font-mono opacity-70">{entry.actorId.slice(0, 8)}…</span>
                        ) : (
                          <span className="text-muted-foreground">system</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{entry.ip ?? '—'}</td>
                      <td className="px-4 py-3 text-center">
                        <span
                          className="text-xs text-primary"
                          aria-label={expanded === entry.id ? 'Collapse' : 'Expand'}
                        >
                          {expanded === entry.id ? '▲' : '▼'}
                        </span>
                      </td>
                    </tr>
                    {expanded === entry.id && (
                      <tr key={`${entry.id}-detail`} className="bg-muted/20">
                        <td colSpan={6} className="px-4 pb-4 pt-2">
                          <div className="grid gap-4 sm:grid-cols-2">
                            <div>
                              <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">
                                Before
                              </p>
                              <pre className="overflow-x-auto rounded bg-muted/40 p-3 text-xs">
                                {formatJson(entry.before)}
                              </pre>
                            </div>
                            <div>
                              <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">
                                After
                              </p>
                              <pre className="overflow-x-auto rounded bg-muted/40 p-3 text-xs">
                                {formatJson(entry.after)}
                              </pre>
                            </div>
                          </div>
                          {entry.requestId && (
                            <p className="mt-2 text-xs text-muted-foreground">
                              Request ID: <span className="font-mono">{entry.requestId}</span>
                            </p>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      <p className="text-xs text-muted-foreground">
        Showing {entries.length} entr{entries.length === 1 ? 'y' : 'ies'} · Audit log is append-only
        and cannot be edited.
      </p>
    </section>
  );
}
