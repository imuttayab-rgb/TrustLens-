/** Chatpanel module in assistant. */
'use client';
import { useEffect, useRef, useState } from 'react';
import { useLocale } from 'next-intl';
import { usePathname } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import {
  ArrowUp,
  Check,
  ChevronDown,
  ExternalLink,
  Globe2,
  Loader2,
  MapPin,
  MessageCircle,
  Minus,
  Package,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Square,
  X,
} from 'lucide-react';
import { LISTING_CATEGORIES, LISTING_CATEGORY_LABELS } from '@trustlens/constants';
import {
  assistantApi,
  type ChatReply,
  type Filters,
  type Listing,
  type Source,
  type Status,
} from './api';

type Message = { id: number; role: 'user' | 'assistant'; text: string; reply?: ChatReply };
const EMPTY_FILTERS: Filters = {
  category: null,
  q: null,
  city: null,
  condition: null,
  minPrice: null,
  maxPrice: null,
  offset: 0,
};
const COMMON_QUESTIONS = [
  {
    en: 'Which options offer the best value within my budget?',
    ur: 'میرے بجٹ میں کون سے اختیارات بہترین قدر فراہم کرتے ہیں؟',
  },
  {
    en: 'Can you help me find listings that match my needs?',
    ur: 'کیا آپ میری ضروریات کے مطابق اشتہارات تلاش کرنے میں مدد کر سکتے ہیں؟',
  },
  {
    en: 'Is this listing fairly priced compared with the market?',
    ur: 'کیا مارکیٹ کے مقابلے میں اس اشتہار کی قیمت مناسب ہے؟',
  },
  {
    en: 'Which specifications matter most for my needs?',
    ur: 'میری ضروریات کے لیے کون سی خصوصیات سب سے زیادہ اہم ہیں؟',
  },
  {
    en: 'What are the key advantages and drawbacks of this product?',
    ur: 'اس پروڈکٹ کے اہم فوائد اور خامیاں کیا ہیں؟',
  },
];

function SourceText({ text, sources }: { text: string; sources: Source[] }) {
  return (
    <div className="whitespace-pre-wrap break-words text-sm leading-7" dir="auto">
      {text.split(/(\[\d+\])/g).map((part, i) => {
        const match = /^\[(\d+)\]$/.exec(part);
        const source = match ? sources.find((s) => s.id === Number(match[1])) : null;
        return source ? (
          <a
            key={i}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mx-0.5 rounded bg-brand/10 px-1 text-xs font-bold text-brand underline underline-offset-2"
            title={source.title}
          >
            {part}
          </a>
        ) : (
          <span key={i}>{part}</span>
        );
      })}
    </div>
  );
}

function ProductCard({
  item,
  selected,
  onSelect,
}: {
  item: Listing;
  selected: boolean;
  onSelect: (item: Listing) => void;
}) {
  return (
    <article className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex gap-3 p-3">
        <Link
          href={item.href}
          className="relative h-20 w-20 shrink-0 overflow-hidden rounded-lg bg-muted"
          aria-label={item.title}
        >
          {item.imageUrl ? (
            <Image
              src={item.imageUrl}
              alt={item.title}
              fill
              unoptimized
              sizes="80px"
              className="object-cover"
            />
          ) : (
            <Package className="m-6 h-8 w-8 text-muted-foreground" />
          )}
        </Link>
        <div className="min-w-0 flex-1">
          <p className="text-base font-bold">
            {item.price == null
              ? 'Price on request'
              : `${item.currency ?? 'PKR'} ${item.price.toLocaleString()}`}
          </p>
          <Link
            href={item.href}
            className="mt-0.5 line-clamp-2 text-sm font-medium hover:text-brand hover:underline"
          >
            {item.title}
          </Link>
          <p className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground">
            <MapPin className="h-3 w-3" />
            {[item.area, item.city].filter(Boolean).join(', ') || 'Location not supplied'}
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {item.condition?.replaceAll('_', ' ') ?? 'Condition not supplied'}
            {item.score != null ? ` · Seller trust ${item.score}/100` : ''}
          </p>
        </div>
      </div>
      <div className="flex items-center justify-between border-t border-border/60 px-3 py-2">
        <button
          type="button"
          aria-pressed={selected}
          onClick={() => onSelect(item)}
          className="flex items-center gap-1.5 text-xs font-medium text-brand"
        >
          <span
            className={`grid h-4 w-4 place-items-center rounded border ${selected ? 'border-brand bg-brand text-primary-foreground' : 'border-input'}`}
          >
            {selected && <Check className="h-3 w-3" />}
          </span>
          Compare
        </button>
        <Link href={item.href} className="text-xs font-semibold text-brand hover:underline">
          View listing →
        </Link>
      </div>
    </article>
  );
}

function AnswerResults({
  reply,
  selected,
  onSelect,
  onUpdate,
}: {
  reply: ChatReply;
  selected: Listing[];
  onSelect: (item: Listing) => void;
  onUpdate: (reply: ChatReply) => void;
}) {
  const ur = useLocale() === 'ur';
  const [tab, setTab] = useState<'listings' | 'market'>(
    reply.listings.items.length ? 'listings' : 'market',
  );
  const [shown, setShown] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const hasResults =
    reply.listings.items.length > 0 ||
    reply.marketOptions.length > 0 ||
    Boolean(reply.listings.nextOffset);
  async function more() {
    setBusy(true);
    setError('');
    try {
      const next = await assistantApi.listings({
        ...reply.listings.filters,
        offset: reply.listings.nextOffset ?? 0,
      });
      const existing = new Set(reply.listings.items.map((x) => x.id));
      onUpdate({
        ...reply,
        listings: {
          ...next,
          items: [...reply.listings.items, ...next.items.filter((x) => !existing.has(x.id))],
        },
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load more.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {hasResults && (
        <div className="mt-4">
          <div
            role="tablist"
            aria-label={ur ? 'تجاویز کا ذریعہ' : 'Recommendation source'}
            className="mb-3 flex rounded-lg bg-muted p-1"
          >
            {(['listings', 'market'] as const).map((value) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={tab === value}
                onClick={() => setTab(value)}
                className={`flex-1 rounded-md px-2 py-2 text-xs font-semibold ${tab === value ? 'bg-card text-brand shadow-sm' : 'text-muted-foreground'}`}
              >
                {value === 'listings'
                  ? ur
                    ? 'ٹرسٹ لینس کے اشتہارات'
                    : 'On TrustLens'
                  : ur
                    ? 'مارکیٹ کے آپشنز'
                    : 'Market options'}
                <span className="ms-1 opacity-60">
                  {value === 'listings' ? reply.listings.items.length : reply.marketOptions.length}
                </span>
              </button>
            ))}
          </div>
          <div role="tabpanel" className="space-y-2.5">
            {tab === 'listings' ? (
              <>
                {!reply.listings.items.length && (
                  <p className="rounded-lg bg-muted p-3 text-xs text-muted-foreground">
                    {ur
                      ? 'ان فلٹرز میں کوئی فعال اشتہار نہیں ملا۔'
                      : 'No active listing matches these filters.'}
                  </p>
                )}
                {reply.listings.items.map((item) => (
                  <ProductCard
                    key={item.id}
                    item={item}
                    selected={selected.some((s) => s.id === item.id)}
                    onSelect={onSelect}
                  />
                ))}
                {reply.listings.nextOffset != null && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void more()}
                    className="flex w-full items-center justify-center gap-2 rounded-lg border border-border py-2.5 text-xs font-semibold text-brand disabled:opacity-50"
                  >
                    {busy ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                    {ur ? 'مزید 3 دکھائیں' : 'Show 3 more listings'}
                  </button>
                )}
              </>
            ) : (
              <>
                <p className="text-[11px] leading-5 text-muted-foreground">
                  {ur
                    ? 'بیرونی ذرائع کی تجاویز۔ یہ ٹرسٹ لینس پر موجود اسٹاک نہیں۔'
                    : 'External product ideas. Availability and prices must be checked with the source.'}
                </p>
                {!reply.marketOptions.length && (
                  <p className="rounded-lg bg-muted p-3 text-xs">
                    {ur
                      ? 'ابھی کوئی ماخذ کے ساتھ آپشن نہیں ملا۔'
                      : 'No sourced market options for this answer.'}
                  </p>
                )}
                {reply.marketOptions.slice(0, shown).map((option, i) => (
                  <article
                    key={`${option.name}-${i}`}
                    className="rounded-xl border border-border bg-card p-3"
                  >
                    <p className="text-sm font-semibold" dir="auto">
                      {option.name}
                    </p>
                    <p className="mt-1 text-xs leading-6 text-muted-foreground" dir="auto">
                      {option.summary}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {option.sourceIds
                        .map((id) => reply.sources.find((s) => s.id === id))
                        .filter((s): s is Source => Boolean(s))
                        .map((s) => (
                          <a
                            key={s.id}
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[11px] font-medium text-brand underline underline-offset-2"
                          >
                            [{s.id}] {new URL(s.url).hostname.replace('www.', '')}
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        ))}
                    </div>
                  </article>
                ))}
                {shown < reply.marketOptions.length && (
                  <button
                    type="button"
                    onClick={() => setShown((s) => s + 3)}
                    className="w-full rounded-lg border border-border py-2 text-xs font-semibold text-brand"
                  >
                    {ur ? 'مزید آپشنز' : 'Show 3 more options'}
                  </button>
                )}
              </>
            )}
          </div>
          {error && (
            <p role="alert" className="mt-2 text-xs text-destructive">
              {error}
            </p>
          )}
        </div>
      )}
      {reply.sources.length > 0 && (
        <details className="mt-3 rounded-lg border border-border px-3 py-2">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
            {ur ? 'ذرائع دیکھیں' : 'Sources checked'} · {reply.sources.length}
          </summary>
          <ol className="mt-2 space-y-2">
            {reply.sources.map((s) => (
              <li key={s.id} className="text-xs">
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand underline"
                >
                  [{s.id}] {s.title}
                </a>
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  {ur ? 'چیک کیا گیا' : 'Checked'} {new Date(s.checkedAt).toLocaleString()}
                </p>
              </li>
            ))}
          </ol>
        </details>
      )}
    </>
  );
}

export default function ChatPanel({
  open,
  onClose,
  prompt,
}: {
  open: boolean;
  onClose: () => void;
  prompt: { text: string; sequence: number };
}) {
  const ur = useLocale() === 'ur';
  const pathname = usePathname();
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);
  const messageId = useRef(0);
  const sending = useRef(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState('');
  const [web, setWeb] = useState(true);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [filterOpen, setFilterOpen] = useState(false);
  const [selected, setSelected] = useState<Listing[]>([]);
  const contextId = /^\/listing\/([a-f\d-]{36})$/i.exec(pathname)?.[1] ?? null;
  useEffect(() => {
    if (open && dialog.current && !dialog.current.open) dialog.current.showModal();
    if (!open) dialog.current?.close();
    if (open) {
      void assistantApi
        .status()
        .then(setStatus)
        .catch(() => setStatus(null));
      const previous = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = previous;
      };
    }
  }, [open]);
  useEffect(() => {
    if (prompt.text) {
      setDraft(prompt.text);
      input.current?.focus();
    }
  }, [prompt]);
  useEffect(() => {
    if (messages.length || busy)
      bottom.current?.scrollIntoView({ behavior: 'auto', block: 'nearest' });
  }, [messages, busy]);
  useEffect(() => () => abort.current?.abort(), []);
  function stop() {
    abort.current?.abort();
    sending.current = false;
    setBusy(false);
  }
  function reset() {
    stop();
    setMessages([]);
    setSelected([]);
    setFilters(EMPTY_FILTERS);
    setError('');
    setDraft('');
  }
  async function send(text: string, compare = false) {
    if (!text.trim() || sending.current) return;
    sending.current = true;
    setBusy(true);
    setError('');
    setDraft('');
    const controller = new AbortController();
    abort.current = controller;
    setMessages((previous) => [
      ...previous,
      { id: ++messageId.current, role: 'user', text: text.trim() },
    ]);
    try {
      const response = await assistantApi.chat(
        {
          message: text.trim().slice(0, 1800),
          history: messages
            .slice(-6)
            .map((m) => ({ role: m.role, content: m.text.slice(0, 1800) })),
          filters,
          currentListingId: contextId,
          compareIds: compare ? selected.map((s) => s.id) : [],
          marketSearch: web,
        },
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setFilters(response.listings.filters);
      setMessages((previous) => [
        ...previous,
        { id: ++messageId.current, role: 'assistant', text: response.answer, reply: response },
      ]);
    } catch (e) {
      if (!controller.signal.aborted) {
        setError(e instanceof Error ? e.message : 'Connection failed. Please try again.');
        setDraft(text);
      }
    } finally {
      if (abort.current === controller) {
        sending.current = false;
        setBusy(false);
      }
    }
  }
  function select(item: Listing) {
    if (selected.length === 3 && !selected.some((x) => x.id === item.id)) {
      setError(ur ? 'ایک وقت میں 3 چیزوں کا موازنہ کریں۔' : 'Compare up to 3 listings at a time.');
      return;
    }
    setSelected((current) => {
      if (current.some((x) => x.id === item.id)) return current.filter((x) => x.id !== item.id);
      if (current.length === 3) return current;
      return [...current, item];
    });
  }
  return (
    <dialog
      ref={dialog}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      aria-labelledby="assistant-title"
      dir={ur ? 'rtl' : 'ltr'}
      className="fixed inset-0 m-0 h-dvh max-h-dvh w-full max-w-none overflow-hidden border-0 bg-card p-0 text-foreground shadow-2xl backdrop:bg-slate-950/25 sm:bottom-5 sm:left-auto sm:right-5 sm:top-auto sm:m-0 sm:h-[min(780px,calc(100dvh-40px))] sm:max-h-[calc(100dvh-40px)] sm:w-[440px] sm:rounded-2xl sm:border sm:border-border print:hidden"
    >
      <div className="flex h-full flex-col">
        <header className="flex shrink-0 items-center gap-3 border-b border-border bg-brand/5 px-4 py-4">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground">
            <Sparkles className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 id="assistant-title" className="text-sm font-bold">
              {ur ? 'ٹرسٹ لینس اسسٹنٹ' : 'TrustLens Assistant'}
            </h2>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              {ur ? 'آپ کی ضرورت، آپ کے بجٹ میں' : 'Find what fits. Buy with clarity.'}
            </p>
          </div>
          <button
            type="button"
            onClick={reset}
            title={ur ? 'نئی گفتگو' : 'New conversation'}
            aria-label="New conversation"
            className="rounded-lg p-2 hover:bg-muted"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label={ur ? 'بند کریں' : 'Minimize assistant'}
            className="rounded-lg p-2 hover:bg-muted"
          >
            <Minus className="h-5 w-5" />
          </button>
        </header>
        <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-4 py-2.5">
          <label className="flex cursor-pointer items-center gap-2 text-xs font-medium">
            <Globe2 className="h-3.5 w-3.5 text-brand" />
            <input
              type="checkbox"
              checked={web}
              onChange={(e) => setWeb(e.target.checked)}
              className="accent-emerald-700"
            />
            {ur ? 'انٹرنیٹ پر بھی تلاش' : 'Include web research'}
          </label>
          <button
            type="button"
            aria-expanded={filterOpen}
            onClick={() => setFilterOpen((x) => !x)}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs hover:bg-muted"
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            {ur ? 'فلٹرز' : 'Filters'}
          </button>
        </div>
        {filterOpen && (
          <div className="grid shrink-0 grid-cols-2 gap-2 border-b border-border bg-muted/40 p-3">
            <label className="col-span-2 text-[11px] text-muted-foreground">
              {ur ? 'قسم' : 'Category'}
              <select
                value={filters.category ?? ''}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    category: e.target.value || null,
                    q: null,
                    offset: 0,
                  }))
                }
                className="mt-1 h-9 w-full rounded-lg border border-input bg-card px-2 text-xs text-foreground"
              >
                <option value="">{ur ? 'تمام اقسام' : 'All categories'}</option>
                {LISTING_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {LISTING_CATEGORY_LABELS[c]}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[11px] text-muted-foreground">
              {ur ? 'زیادہ سے زیادہ بجٹ (PKR)' : 'Maximum budget (PKR)'}
              <input
                type="number"
                min="0"
                max="1000000000"
                value={filters.maxPrice ?? ''}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    maxPrice: e.target.value
                      ? Math.max(0, Math.min(1e9, Number(e.target.value)))
                      : null,
                    offset: 0,
                  }))
                }
                className="mt-1 h-9 w-full rounded-lg border border-input bg-card px-2 text-xs text-foreground"
              />
            </label>
            <label className="text-[11px] text-muted-foreground">
              {ur ? 'شہر' : 'City'}
              <input
                value={filters.city ?? ''}
                maxLength={80}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, city: e.target.value || null, offset: 0 }))
                }
                placeholder="Lahore"
                className="mt-1 h-9 w-full rounded-lg border border-input bg-card px-2 text-xs text-foreground"
              />
            </label>
            <button
              type="button"
              onClick={() => setFilters(EMPTY_FILTERS)}
              className="col-span-2 text-start text-xs text-brand underline"
            >
              {ur ? 'فلٹرز صاف کریں' : 'Clear filters'}
            </button>
          </div>
        )}
        {contextId && (
          <p className="shrink-0 border-b border-border bg-brand/5 px-4 py-2 text-[11px] text-brand">
            {ur
              ? 'اس اشتہار کے بارے میں بھی پوچھ سکتے ہیں۔'
              : 'You can ask about the listing you are viewing.'}
          </p>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5">
          {messages.length === 0 && (
            <div className="py-3">
              <span className="mb-4 inline-flex rounded-full border border-brand/20 bg-brand/5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-brand">
                {ur ? 'خریداری میں رہنمائی' : 'Shopping assistance'}
              </span>
              <h3 className="text-2xl font-bold tracking-tight">
                {ur ? 'ہم آپ کی کیا مدد کر سکتے ہیں؟' : 'How can we help you?'}
              </h3>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                {ur
                  ? 'تمام زمروں میں اشتہارات تلاش کرنے، خصوصیات سمجھنے اور مختلف اختیارات کا موازنہ کرنے میں مدد حاصل کریں۔'
                  : 'Get help finding listings, understanding specifications and comparing options across all categories.'}
              </p>
              <p className="mb-2 mt-5 text-xs font-semibold text-muted-foreground">
                {ur ? 'عام سوالات' : 'Common questions'}
              </p>
              <div id="trustlens-common-questions" className="space-y-2">
                {COMMON_QUESTIONS.map((question) => (
                  <button
                    key={question.en}
                    type="button"
                    onClick={() => {
                      setDraft(ur ? question.ur : question.en);
                      input.current?.focus();
                    }}
                    className="flex min-h-11 w-full items-center justify-between gap-3 rounded-xl border border-border p-3 text-start text-xs leading-5 transition-colors hover:border-brand/40 hover:bg-brand/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span>{ur ? question.ur : question.en}</span>
                    <MessageCircle className="h-3.5 w-3.5 shrink-0 text-brand" />
                  </button>
                ))}
              </div>
              {status && !status.ready && (
                <p className="mt-4 rounded-lg bg-muted p-3 text-xs leading-5 text-muted-foreground">
                  {ur
                    ? 'AI ابھی منسلک نہیں۔ آپ اشتہارات تلاش کر سکتے ہیں۔'
                    : 'AI is not connected yet. Listing search is still available.'}
                </p>
              )}
              {status?.ready && !status.webReady && (
                <p className="mt-4 text-xs leading-5 text-muted-foreground">
                  {ur
                    ? 'ویب سرچ ابھی دستیاب نہیں۔'
                    : 'AI is configured; live web research is not configured yet.'}
                </p>
              )}
            </div>
          )}
          <div className="space-y-5" aria-live="polite" aria-relevant="additions">
            {messages.map((message) =>
              message.role === 'user' ? (
                <div
                  key={message.id}
                  className="ms-7 rounded-2xl rounded-ee-sm bg-primary px-4 py-3 text-sm leading-6 text-primary-foreground"
                  dir="auto"
                >
                  {message.text}
                </div>
              ) : (
                <section key={message.id} className="me-1">
                  <p className="mb-2 flex items-center gap-1.5 text-[11px] font-bold text-brand">
                    <Sparkles className="h-3.5 w-3.5" />
                    TrustLens{message.reply?.mode === 'listings-only' ? ' · Listing search' : ''}
                  </p>
                  <SourceText text={message.text} sources={message.reply?.sources ?? []} />
                  {message.reply?.warnings.map((warning, i) => (
                    <p
                      key={i}
                      className="mt-2 rounded-lg bg-muted px-3 py-2 text-[11px] leading-5 text-muted-foreground"
                    >
                      {warning}
                    </p>
                  ))}
                  {message.reply && (
                    <AnswerResults
                      reply={message.reply}
                      selected={selected}
                      onSelect={select}
                      onUpdate={(reply) =>
                        setMessages((previous) =>
                          previous.map((m) => (m.id === message.id ? { ...m, reply } : m)),
                        )
                      }
                    />
                  )}
                </section>
              ),
            )}
            {busy && (
              <p className="flex items-center gap-2 text-xs text-muted-foreground" role="status">
                <Loader2 className="h-4 w-4 animate-spin text-brand" />
                {ur
                  ? 'آپ کے سوال اور دستیاب معلومات کو دیکھ رہا ہوں…'
                  : 'Checking your request and available information…'}
              </p>
            )}
          </div>
          <div ref={bottom} />
        </div>
        {selected.length > 0 && (
          <div className="shrink-0 border-t border-border bg-brand/5 px-4 py-2">
            <div className="flex flex-wrap gap-1">
              {selected.map((s) => (
                <button
                  key={s.id}
                  onClick={() => select(s)}
                  type="button"
                  className="flex max-w-[180px] items-center gap-1 rounded-full border border-brand/20 bg-card px-2 py-1 text-[10px]"
                >
                  <span className="truncate">{s.title}</span>
                  <X className="h-3 w-3 shrink-0" />
                </button>
              ))}
            </div>
            <button
              type="button"
              disabled={selected.length < 2 || busy}
              onClick={() =>
                void send(
                  ur
                    ? 'ان منتخب چیزوں کا موازنہ کریں۔ خوبیوں، خامیوں اور نامعلوم تفصیلات کو واضح کریں۔'
                    : 'Compare these selected listings. Explain suitability, compromises, missing facts and questions for the seller.',
                  true,
                )
              }
              className="mt-2 text-xs font-semibold text-brand disabled:opacity-40"
            >
              {ur ? 'منتخب چیزوں کا موازنہ' : `Compare ${selected.length} selected listings`} →
            </button>
          </div>
        )}
        <footer className="shrink-0 border-t border-border bg-card px-4 pb-[max(12px,env(safe-area-inset-bottom))] pt-3">
          {error && (
            <p role="alert" className="mb-2 text-xs text-destructive">
              {error}
            </p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send(draft);
            }}
            className="flex items-end gap-2 rounded-xl border border-input bg-background p-2 focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/10"
          >
            <textarea
              ref={input}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={1800}
              rows={2}
              dir="auto"
              aria-label={ur ? 'اپنا سوال لکھیں' : 'Message the assistant'}
              placeholder={ur ? 'اپنا بجٹ اور ضرورت بتائیں…' : 'Your budget, product, or question…'}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  void send(draft);
                }
              }}
              className="max-h-28 min-h-12 min-w-0 flex-1 resize-none bg-transparent p-1 text-sm outline-none placeholder:text-muted-foreground"
            />
            {busy ? (
              <button
                type="button"
                onClick={stop}
                aria-label="Stop response"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-muted"
              >
                <Square className="h-4 w-4" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!draft.trim()}
                aria-label={ur ? 'بھیجیں' : 'Send message'}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground disabled:opacity-35"
              >
                <ArrowUp className="h-5 w-5" />
              </button>
            )}
          </form>
          <p className="mt-2 flex items-center justify-center gap-1 text-center text-[10px] text-muted-foreground">
            <ShieldCheck className="h-3 w-3" />
            {ur
              ? 'اہم تفصیلات خود چیک کریں۔ ذاتی دستاویزات شیئر نہ کریں۔'
              : 'Check important details. Keep personal documents private.'}
          </p>
        </footer>
      </div>
    </dialog>
  );
}
