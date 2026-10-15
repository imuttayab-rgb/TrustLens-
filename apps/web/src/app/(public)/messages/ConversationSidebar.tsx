/** Next.js route/layout composition for (public)/messages: ConversationSidebar. */
'use client';

import { ProfileAvatar } from '@/features/profile';
import { useConversations, useSetConversationImportant } from '@/features/messaging';
import { RISK_PRESENTATION, type RiskLevel } from '@trustlens/constants';
import { Spinner } from '@trustlens/ui';
import { cn, formatRelative } from '@trustlens/utils';
import { Search, Star } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useLocale } from 'next-intl';

type Tab = 'all' | 'buying' | 'selling' | 'unread' | 'important';

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

export function ConversationSidebar() {
  const ur = useLocale() === 'ur';
  const important = useSetConversationImportant();
  const pathname = usePathname();
  const activeId = pathname.startsWith('/messages/') ? pathname.split('/')[2] : null;
  const [tab, setTab] = useState<Tab>('all');
  const [query, setQuery] = useState('');

  const [debounced, setDebounced] = useState('');
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(query);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);
  const { data, isPending, isError, refetch } = useConversations({
    folder: tab,
    q: debounced,
    offset,
    limit: 20,
  });
  const filtered = data?.items ?? [];

  return (
    <div className="flex h-full flex-col border-e border-border">
      <div className="p-3">
        <div className="relative">
          <Search
            className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={ur ? 'پیغامات تلاش کریں' : 'Search messages'}
            aria-label={ur ? 'پیغامات تلاش کریں' : 'Search messages'}
            className="h-10 w-full rounded-md border border-input bg-background pe-3 ps-9 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>

        <div className="mt-3 flex flex-wrap gap-1 border-b border-border">
          {(
            [
              { key: 'all', label: 'All' },
              { key: 'buying', label: 'Buying' },
              { key: 'selling', label: 'Selling' },
              { key: 'unread', label: 'Unread' },
              { key: 'important', label: 'Important' },
            ] as const
          ).map((t) => (
            <button
              key={t.key}
              type="button"
              aria-pressed={tab === t.key}
              onClick={() => {
                setTab(t.key);
                setOffset(0);
              }}
              className={cn(
                'relative px-3 py-2 text-sm font-medium transition-colors',
                tab === t.key ? 'text-brand' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {ur
                ? {
                    all: 'تمام',
                    buying: 'خریداری',
                    selling: 'فروخت',
                    unread: 'نہیں پڑھے',
                    important: 'اہم',
                  }[t.key]
                : t.label}
              {tab === t.key && (
                <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand" />
              )}
            </button>
          ))}
        </div>
      </div>

      {important.isError && (
        <p role="alert" className="px-3 py-2 text-xs text-destructive">
          {ur
            ? 'اہم کا نشان محفوظ نہیں ہوا۔ دوبارہ کوشش کریں۔'
            : 'Could not save the important marker. Try again.'}
        </p>
      )}
      <div className="flex-1 overflow-y-auto">
        {isPending ? (
          <div className="flex justify-center py-10">
            <Spinner label="Loading conversations" />
          </div>
        ) : isError ? (
          <p className="px-3 py-6 text-center text-sm text-destructive">
            <button type="button" onClick={() => void refetch()}>
              {ur
                ? 'پیغامات لوڈ نہیں ہوئے۔ دوبارہ کوشش کریں۔'
                : 'Could not load your messages. Try again.'}
            </button>
          </p>
        ) : filtered.length === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-muted-foreground">
            {ur
              ? 'اس فلٹر میں کوئی گفتگو نہیں ملی۔'
              : 'No conversations match this folder or search.'}
          </p>
        ) : (
          <ul>
            {filtered.map((c) => (
              <li key={c.id}>
                <div
                  className={cn(
                    'flex items-start gap-3 border-b border-border/60 p-3 transition-colors hover:bg-muted/60',
                    activeId === c.id && 'bg-brand/5',
                  )}
                >
                  <Link
                    href={c.counterpartProfileUrl ?? `/profile/${c.counterpartUserId}`}
                    aria-label={`View ${c.counterpartName}'s profile`}
                    className="shrink-0 rounded-full focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <ProfileAvatar
                      src={c.counterpartAvatarUrl}
                      name={c.counterpartName}
                      size={44}
                    />
                  </Link>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <Link
                        href={c.counterpartProfileUrl ?? `/profile/${c.counterpartUserId}`}
                        className="truncate text-sm font-semibold hover:underline"
                      >
                        {c.counterpartName}
                      </Link>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {formatRelative(c.lastMessageAt)}
                      </span>
                    </div>
                    <Link
                      href={`/messages/${c.id}`}
                      className="mt-0.5 block truncate text-sm text-muted-foreground hover:underline"
                    >
                      {c.lastMessagePreview ?? (ur ? 'گفتگو کھولیں' : 'Open conversation')}
                    </Link>
                    <div className="mt-1 flex items-center gap-2">
                      <button
                        type="button"
                        aria-pressed={c.important ?? false}
                        aria-label={
                          c.important
                            ? ur
                              ? 'اہم کا نشان ہٹائیں'
                              : 'Remove important marker'
                            : ur
                              ? 'اہم نشان لگائیں'
                              : 'Mark important'
                        }
                        disabled={
                          important.isPending && important.variables?.conversationId === c.id
                        }
                        onClick={() =>
                          important.mutate({ conversationId: c.id, important: !c.important })
                        }
                        className="grid h-9 w-9 place-items-center rounded-lg hover:bg-muted disabled:opacity-50"
                      >
                        <Star
                          className={cn('h-4 w-4', c.important && 'fill-amber-400 text-amber-500')}
                          aria-hidden="true"
                        />
                      </button>
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
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      {(offset > 0 || (data?.total ?? 0) > offset + 20) && (
        <nav
          aria-label={ur ? 'گفتگو کے صفحات' : 'Conversation pages'}
          className="flex justify-between border-t border-border p-3 text-sm"
        >
          <button
            type="button"
            disabled={offset === 0 || isPending}
            onClick={() => setOffset((v) => Math.max(0, v - 20))}
            className="rounded-lg border border-border px-3 py-2 disabled:opacity-40"
          >
            {ur ? 'پچھلا' : 'Previous'}
          </button>
          <button
            type="button"
            disabled={(data?.total ?? 0) <= offset + 20 || isPending}
            onClick={() => setOffset((v) => v + 20)}
            className="rounded-lg border border-border px-3 py-2 disabled:opacity-40"
          >
            {ur ? 'اگلا' : 'Next'}
          </button>
        </nav>
      )}
    </div>
  );
}
