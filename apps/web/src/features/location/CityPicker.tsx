/** Citypicker module; defines CityPicker. */
'use client';

import { Check, ChevronDown, MapPin, Search, X } from 'lucide-react';
import { useLocale } from 'next-intl';
import { useEffect, useId, useRef, useState } from 'react';

interface Props {
  value: string;
  onChange: (city: string) => void;
  cities: readonly string[];
  province?: string | null;
  placeholder?: string;
  required?: boolean;
  allowOther?: boolean;
  align?: 'start' | 'end';
  className?: string;
}

function normalized(value: string) {
  return value
    .normalize('NFKD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '');
}

const CITY_ALIASES: Record<string, string> = {
  lhr: 'Lahore',
  khi: 'Karachi',
  isb: 'Islamabad',
  rwp: 'Rawalpindi',
  fsd: 'Faisalabad',
  ryk: 'Rahim Yar Khan',
  dgk: 'Dera Ghazi Khan',
};

/** Search filters the supplied region's cities locally; only a chosen option becomes a city. */
export function CityPicker({
  value,
  onChange,
  cities,
  province,
  placeholder = 'Select city',
  required = false,
  allowOther = false,
  align = 'start',
  className = '',
}: Props) {
  const ur = useLocale() === 'ur';
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [index, setIndex] = useState(0);
  const [invalid, setInvalid] = useState(false);
  const options = [
    ...new Set([
      ...cities.filter((city) => city !== 'Other'),
      ...(value && value !== 'Other' && !cities.includes(value) ? [value] : []),
      ...(allowOther || value === 'Other' ? ['Other'] : []),
    ]),
  ];
  const needle = normalized(query);
  const alias = CITY_ALIASES[needle];
  const filtered = options.filter((city) => normalized(city).includes(needle) || city === alias);
  const cityLabel = ur ? 'شہر' : 'City';

  useEffect(() => {
    setOpen(false);
    setQuery('');
    setIndex(0);
    setInvalid(false);
  }, [province]);

  useEffect(() => {
    if (!open) return;
    input.current?.focus();
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === 'Escape' && root.current?.contains(event.target as Node)) {
        event.preventDefault();
        event.stopPropagation();
        setOpen(false);
        trigger.current?.focus();
      }
    }
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  useEffect(() => {
    if (open) document.getElementById(`${id}-city-${index}`)?.scrollIntoView({ block: 'nearest' });
  }, [id, index, open, query]);

  function choose(city: string) {
    onChange(city);
    setOpen(false);
    setInvalid(false);
    setQuery('');
    trigger.current?.focus();
  }

  function show() {
    setQuery('');
    setIndex(0);
    setOpen((previous) => !previous);
  }

  return (
    <div
      ref={root}
      className="relative min-w-0"
      onBlur={(event) => {
        if (event.relatedTarget && !root.current?.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      {/* Keep native form validation without exposing a second selector to assistive technology. */}
      <select
        aria-hidden="true"
        aria-label="Selected city value"
        tabIndex={-1}
        className="sr-only pointer-events-none"
        value={value}
        required={required}
        onChange={(event) => choose(event.target.value)}
        onInvalid={(event) => {
          event.preventDefault();
          setInvalid(true);
          setOpen(true);
        }}
      >
        <option value="">{placeholder}</option>
        {options.map((city) => (
          <option key={city} value={city}>
            {city}
          </option>
        ))}
      </select>
      <button
        ref={trigger}
        type="button"
        aria-label={`${cityLabel}: ${value || placeholder}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? `${id}-dialog` : undefined}
        onClick={show}
        className={`flex w-full min-w-0 items-center gap-2 text-start font-normal outline-none focus-visible:ring-2 focus-visible:ring-ring ${className}`}
      >
        <MapPin className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className={`min-w-0 flex-1 truncate ${value ? '' : 'text-muted-foreground'}`}>
          {value || placeholder}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      </button>
      {open && (
        <div
          id={`${id}-dialog`}
          role="dialog"
          aria-label={ur ? 'شہر منتخب کریں' : 'Choose a city'}
          className={`absolute top-full z-50 mt-2 w-full min-w-[min(16rem,calc(100vw-3rem))] overflow-hidden rounded-xl border border-border bg-card text-card-foreground shadow-xl ${align === 'end' ? 'end-0' : 'start-0'}`}
        >
          <div className="border-b border-border p-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              {province || (ur ? 'پورا پاکستان' : 'All Pakistan')}
            </p>
            <div className="flex items-center gap-2 rounded-lg border border-input bg-background px-2.5 focus-within:ring-2 focus-within:ring-ring">
              <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <input
                ref={input}
                role="combobox"
                aria-label={ur ? 'شہر تلاش کریں' : 'Search city'}
                aria-autocomplete="list"
                aria-invalid={invalid || undefined}
                aria-expanded={open}
                aria-controls={`${id}-list`}
                aria-activedescendant={filtered[index] ? `${id}-city-${index}` : undefined}
                autoComplete="off"
                placeholder={ur ? 'شہر کا نام لکھیں…' : 'Type a city name…'}
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setIndex(0);
                }}
                className="h-10 min-w-0 flex-1 bg-transparent text-sm font-normal outline-none"
                onKeyDown={(event) => {
                  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                    event.preventDefault();
                    setIndex((previous) =>
                      Math.max(
                        0,
                        Math.min(
                          filtered.length - 1,
                          previous + (event.key === 'ArrowDown' ? 1 : -1),
                        ),
                      ),
                    );
                  }
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    if (filtered[index]) choose(filtered[index]);
                  }
                  if (event.key === 'Home' && event.ctrlKey) {
                    event.preventDefault();
                    setIndex(0);
                  }
                  if (event.key === 'End' && event.ctrlKey) {
                    event.preventDefault();
                    setIndex(Math.max(0, filtered.length - 1));
                  }
                }}
              />
              {query && (
                <button
                  type="button"
                  aria-label={ur ? 'تلاش صاف کریں' : 'Clear city search'}
                  onClick={() => {
                    setQuery('');
                    setIndex(0);
                    input.current?.focus();
                  }}
                  className="rounded p-1 text-muted-foreground hover:bg-muted"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              )}
            </div>
            {invalid && (
              <p className="mt-2 text-xs text-destructive" role="alert">
                {ur ? 'فہرست سے شہر منتخب کریں۔' : 'Choose a city from the list.'}
              </p>
            )}
          </div>
          <ul
            id={`${id}-list`}
            role="listbox"
            aria-label={cityLabel}
            className="max-h-56 overflow-y-auto overscroll-contain p-1"
          >
            {filtered.map((city, i) => (
              <li
                id={`${id}-city-${i}`}
                key={city}
                role="option"
                aria-selected={value === city}
                className={`flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-normal ${i === index ? 'bg-brand/10 text-brand' : 'hover:bg-muted'}`}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(city)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    choose(city);
                  }
                }}
              >
                <span className="min-w-0 flex-1 break-words">
                  {city === 'Other' ? (ur ? 'دیگر / فہرست میں نہیں' : 'Other / not listed') : city}
                </span>
                {value === city && <Check className="h-4 w-4 shrink-0" aria-hidden="true" />}
              </li>
            ))}
          </ul>
          <p
            role="status"
            aria-live="polite"
            className="border-t border-border px-3 py-2 text-xs font-normal text-muted-foreground"
          >
            {filtered.length
              ? ur
                ? `${filtered.length} شہر`
                : `${filtered.length} ${filtered.length === 1 ? 'city' : 'cities'}`
              : ur
                ? 'کوئی شہر نہیں ملا۔ ہجے تبدیل کر کے دیکھیں۔'
                : 'No cities found. Try another spelling.'}
          </p>
          {value && (
            <button
              type="button"
              onClick={() => choose('')}
              className="w-full border-t border-border px-3 py-2.5 text-sm font-medium text-brand hover:bg-muted"
            >
              {ur ? 'منتخب شہر ہٹائیں' : 'Clear city selection'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
