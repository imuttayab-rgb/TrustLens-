'use client';

import { useConversations, type ConversationSummary } from '@/features/messaging';
import { RISK_PRESENTATION, type RiskLevel } from '@trustlens/constants';
import { Spinner } from '@trustlens/ui';
import { cn, formatRelative } from '@trustlens/utils';
import { Search } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useMemo, useState } from 'react';

type Tab = 'all' | 'buying' | 'selling';

const TRUST_PILL_COLOR: Record<RiskLevel, string> = {
  LOW: 'border-risk-low text-risk-low',
  MEDIUM: 'border-risk-medium text-risk-medium',
  HIGH: 'border-risk-high text-risk-high',
  UNKNOWN: 'border-risk-unknown text-risk-unknown',
};

function TrustPill({ riskLevel, score }: { riskLevel: RiskLevel; score: number | null }) {
  return (
    <span
      className={cn(
        'shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-bold',
        TRUST_PILL_COLOR[riskLevel],
      )}
    >
      {score !== null ? `Trust ${score}` : RISK_PRESENTATION[riskLevel].label}
    </span>
  );
}

function isBuying(c: ConversationSummary): boolean {
  return c.counterpartSellerHandle !== null;
}

export function ConversationSidebar() {
  const { data, isPending, isError } = useConversations();
  const pathname = usePathname();
  const activeId = pathname.startsWith('/messages/') ? pathname.split('/')[2] : null;
  const [tab, setTab] = useState<Tab>('all');
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    let items = data?.items ?? [];
    if (tab === 'buying') items = items.filter(isBuying);
    if (tab === 'selling') items = items.filter((c) => !isBuying(c));
    const q = query.trim().toLowerCase();
    if (q) {
      items = items.filter(
        (c) =>
          c.counterpartName.toLowerCase().includes(q) ||
          (c.listingTitle?.toLowerCase().includes(q) ?? false),
      );
    }
    return items;
  }, [data, tab, query]);

  return (
    <div className="flex h-full flex-col border-r border-border">
      <div className="p-3">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search messages"
            aria-label="Search messages"
            className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>

        <div className="mt-3 flex gap-1 border-b border-border">
          {(
            [
              { key: 'all', label: 'All' },
              { key: 'buying', label: 'Buying' },
              { key: 'selling', label: 'Selling' },
            ] as const
          ).map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={cn(
                'relative px-3 py-2 text-sm font-medium transition-colors',
                tab === t.key ? 'text-brand' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {t.label}
              {tab === t.key && (
                <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand" />
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isPending ? (
          <div className="flex justify-center py-10">
            <Spinner label="Loading conversations" />
          </div>
        ) : isError ? (
          <p className="px-3 py-6 text-center text-sm text-destructive">
            Could not load your messages.
          </p>
        ) : filtered.length === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-muted-foreground">
            {query ? 'No conversations match your search.' : 'No conversations yet.'}
          </p>
        ) : (
          <ul>
            {filtered.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/messages/${c.id}`}
                  className={cn(
                    'flex items-start gap-3 border-b border-border/60 p-3 transition-colors hover:bg-muted/60',
                    activeId === c.id && 'bg-brand/5',
                  )}
                >
                  <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-brand/10 text-sm font-bold text-brand">
                    {c.counterpartName.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-sm font-semibold">{c.counterpartName}</p>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {formatRelative(c.lastMessageAt)}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-sm text-muted-foreground">
                      {c.lastMessagePreview ?? 'No messages yet'}
                    </p>
                    <div className="mt-1 flex items-center gap-2">
                      {c.unreadCount > 0 && (
                        <span className="grid h-5 min-w-5 place-items-center rounded-full bg-brand px-1 text-[11px] font-bold text-[hsl(var(--background))]">
                          {c.unreadCount}
                        </span>
                      )}
                      {c.counterpartRiskLevel && (
                        <TrustPill
                          riskLevel={c.counterpartRiskLevel as RiskLevel}
                          score={c.counterpartScore}
                        />
                      )}
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
