/** Smartsearch module; defines SmartSearch. */
'use client';
import { useEffect, useId, useRef, useState } from 'react';
import { useLocale } from 'next-intl';
import { Search, ArrowUpLeft, Package } from 'lucide-react';
import { LISTING_CATEGORY_LABELS, type ListingCategory } from '@trustlens/constants';
import { assistantApi, type Suggestions } from './api';

interface Props {
  value: string;
  onChange: (value: string) => void;
  category?: string | null;
  city?: string | null;
  seller?: boolean;
  placeholder?: string;
  label?: string;
  className?: string;
  maxLength?: number;
  invalid?: boolean;
  onSelect?: (value: string, category: string | null) => void;
  onFocus?: () => void;
  onBlur?: () => void;
}

/** No model call on keystrokes. Suggestions combine eligible ads and vocabulary. */
export function SmartSearch({
  value,
  onChange,
  category = null,
  city = null,
  seller = false,
  placeholder = 'Search products, brands or models',
  label = 'Search products',
  className = '',
  maxLength = 80,
  invalid = false,
  onSelect,
  onFocus,
  onBlur,
}: Props) {
  const id = useId();
  const ur = useLocale() === 'ur';
  const root = useRef<HTMLDivElement>(null);
  const [focused, setFocused] = useState(false);
  const [items, setItems] = useState<Suggestions['items']>([]);
  const [index, setIndex] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [total, setTotal] = useState(0);
  const [failed, setFailed] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => {
    if (!focused) return;
    const controller = new AbortController();
    request.current = controller;
    setLoading(false);
    setFailed(false);
    setNextOffset(null);
    setTotal(0);
    setItems([]);
    setIndex(-1);
    const timer = window.setTimeout(() => {
      setLoading(true);
      void assistantApi
        .suggestions(value.trim(), category, city, seller, controller.signal)
        .then((data) => {
          if (!controller.signal.aborted) {
            setItems(data.items);
            setTotal(data.total);
            setNextOffset(data.nextOffset);
          }
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setItems([]);
            setFailed(true);
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 280);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value, category, city, seller, focused]);
  useEffect(() => {
    if (index >= 0) document.getElementById(`${id}-${index}`)?.scrollIntoView({ block: 'nearest' });
  }, [id, index]);
  async function showMore() {
    const controller = request.current;
    if (nextOffset === null || loading || !controller || controller.signal.aborted) return;
    setLoading(true);
    setFailed(false);
    try {
      const data = await assistantApi.suggestions(
        value.trim(),
        category,
        city,
        seller,
        controller.signal,
        nextOffset,
      );
      if (controller.signal.aborted) return;
      setItems((previous) => {
        const seen = new Set(previous.map((item) => `${item.category}-${item.text}`));
        return [
          ...previous,
          ...data.items.filter((item) => !seen.has(`${item.category}-${item.text}`)),
        ];
      });
      setTotal(data.total);
      setNextOffset(data.nextOffset);
    } catch {
      if (!controller.signal.aborted) setFailed(true);
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }
  const open = focused && (loading || items.length > 0 || failed);
  function choose(item: Suggestions['items'][number]) {
    const query = seller ? item.text : (item.query ?? item.text);
    onChange(query);
    onSelect?.(query, item.category ?? null);
    setFocused(false);
    setIndex(-1);
  }
  return (
    <div
      ref={root}
      className="relative min-w-0 flex-1"
      onBlur={(event) => {
        if (!root.current?.contains(event.relatedTarget)) {
          setFocused(false);
          onBlur?.();
        }
      }}
    >
      <input
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={`${id}-options`}
        aria-activedescendant={open && index >= 0 ? `${id}-${index}` : undefined}
        aria-label={label}
        aria-invalid={invalid}
        value={value}
        maxLength={maxLength}
        autoComplete="off"
        placeholder={placeholder}
        className={className}
        onChange={(event) => {
          onChange(event.target.value);
          setFocused(true);
        }}
        onClick={() => setFocused(true)}
        onFocus={() => {
          setFocused(true);
          onFocus?.();
        }}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setFocused(false);
            event.stopPropagation();
          }
          if (open && event.key === 'ArrowDown') {
            event.preventDefault();
            setIndex((i) => Math.min(i + 1, items.length - 1));
          }
          if (open && event.key === 'ArrowUp') {
            event.preventDefault();
            setIndex((i) => Math.max(i - 1, 0));
          }
          if (open && event.key === 'Enter' && index >= 0 && items[index]) {
            event.preventDefault();
            choose(items[index]);
          }
        }}
      />
      {open && (
        <div className="absolute left-0 right-0 top-full z-40 mt-2 overflow-hidden rounded-xl border border-border bg-card shadow-xl">
          <p className="border-b border-border px-3 py-2 text-[11px] font-medium text-muted-foreground">
            {ur ? 'مصنوعات اور ماڈلز کی تجاویز' : 'Products & model suggestions'}
          </p>
          <ul
            id={`${id}-options`}
            role="listbox"
            aria-label={label}
            className="max-h-64 overflow-auto p-1"
          >
            {items.map((item, i) => (
              <li
                key={`${item.category}-${item.kind}-${item.text}`}
                id={`${id}-${i}`}
                role="option"
                aria-selected={index === i}
                className={`flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2.5 text-sm ${index === i ? 'bg-brand/10 text-brand' : 'hover:bg-muted'}`}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(item)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    choose(item);
                  }
                }}
              >
                {item.kind === 'listing' ? (
                  <Package className="h-4 w-4 shrink-0 text-brand" />
                ) : (
                  <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
                )}
                <span className="min-w-0 flex-1">
                  <span className="block break-words">{item.text}</span>
                  {!category && item.category && (
                    <span className="block text-[10px] text-muted-foreground">
                      {LISTING_CATEGORY_LABELS[item.category as ListingCategory] ?? item.category}
                    </span>
                  )}
                </span>
                <span
                  className={`${item.kind === 'listing' ? '' : 'hidden sm:block'} shrink-0 text-[10px] text-muted-foreground`}
                >
                  {item.kind === 'listing'
                    ? ur
                      ? 'اشتہار'
                      : 'Live ad'
                    : ur
                      ? 'تجویز'
                      : 'Suggestion'}
                </span>
                <ArrowUpLeft className="h-3 w-3 shrink-0 text-muted-foreground" />
              </li>
            ))}
            {loading && (
              <li className="px-3 py-2 text-xs text-muted-foreground" role="presentation">
                {ur ? 'تلاش جاری ہے…' : 'Finding suggestions…'}
              </li>
            )}
          </ul>
          {failed && (
            <p className="px-3 py-2 text-xs text-muted-foreground" role="status">
              {ur
                ? 'تجاویز دستیاب نہیں۔ آپ اپنی تلاش لکھ سکتے ہیں۔'
                : 'Suggestions could not load. You can still type your search.'}
            </p>
          )}
          {nextOffset !== null && (
            <button
              type="button"
              disabled={loading}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => void showMore()}
              className="w-full border-t border-border px-3 py-3 text-sm font-medium text-brand hover:bg-muted disabled:opacity-50"
            >
              {loading
                ? ur
                  ? 'تلاش جاری ہے…'
                  : 'Loading…'
                : ur
                  ? 'مزید تجاویز دیکھیں'
                  : `Show more suggestions (${items.length} of ${total})`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
