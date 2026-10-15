/** Megamenu module; defines MegaMenu. */
'use client';
import { useEffect, useId, useRef, useState } from 'react';
import { useLocale } from 'next-intl';
import { usePathname, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import { ChevronDown, X, Search, ArrowLeft } from 'lucide-react';
import {
  MARKETPLACE_ROOTS,
  MARKETPLACE_NODES,
  categoryChildren,
  categoryBrowseHref,
  categoryPath,
  type CategoryNode,
} from '@trustlens/constants';
import { useBrowseContext } from '@/features/marketplace';

/** Wide, opaque category directory. Every level remains reachable without hover. */
export function MegaMenu() {
  const ur = useLocale() === 'ur';
  const context = useBrowseContext();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [shown, setShown] = useState(60);
  const [top, setTop] = useState(230);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const pathname = usePathname();
  const params = useSearchParams();
  useEffect(() => setOpen(false), [pathname, params]);
  useEffect(() => {
    if (!open) return;
    const header = root.current?.closest('header');
    const position = () => setTop(Math.max(8, (header?.getBoundingClientRect().bottom ?? 220) + 8));
    position();
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(position);
    if (header) observer?.observe(header);
    const outside = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', key);
    window.addEventListener('resize', position);
    window.addEventListener('scroll', position, { passive: true });
    return () => {
      observer?.disconnect();
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', key);
      window.removeEventListener('resize', position);
      window.removeEventListener('scroll', position);
    };
  }, [open]);
  const label = (n: CategoryNode) => (ur ? n.labelUr : n.label);
  const needle = query.trim().toLocaleLowerCase();
  const matches = needle
    ? MARKETPLACE_NODES.filter(
        (n) =>
          n.selectable &&
          categoryPath(n.id).some((p) =>
            `${p.label} ${p.labelUr}`.toLocaleLowerCase().includes(needle),
          ),
      )
    : [];
  const groups = selected ? MARKETPLACE_ROOTS.filter((n) => n.id === selected) : MARKETPLACE_ROOTS;
  const close = () => {
    setOpen(false);
    trigger.current?.focus();
  };
  return (
    <div
      ref={root}
      className="relative"
      onBlur={(e) => {
        if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) setOpen(false);
      }}
    >
      <button
        ref={trigger}
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex min-h-10 items-center gap-2 rounded-lg px-2 text-sm font-medium"
      >
        {ur ? 'تمام اقسام' : 'All categories'}
        <ChevronDown className="h-4 w-4" aria-hidden="true" />
      </button>
      {open && (
        <section
          id={id}
          className="tl-mega-panel rounded-2xl border border-border p-4 shadow-xl sm:p-6"
          style={{ '--mega-top': `${top}px` } as React.CSSProperties}
          aria-label={ur ? 'تمام اقسام' : 'All categories'}
        >
          <div className="mb-5 flex flex-wrap items-center gap-3 border-b border-border pb-4">
            <div className="me-auto">
              <h2 className="text-lg font-semibold">
                {ur ? 'ہر ضرورت کے لیے ایک جگہ' : 'Explore the marketplace'}
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                {context.city || (ur ? 'پورا پاکستان' : 'All Pakistan')} ·{' '}
                {ur ? 'تمام اقسام اور ذیلی اقسام' : 'All categories and subcategories'}
              </p>
            </div>
            <label className="order-3 flex w-full items-center gap-2 rounded-xl border border-input bg-background px-3 sm:order-none sm:w-72">
              <Search className="h-4 w-4" aria-hidden="true" />
              <input
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setShown(60);
                }}
                className="h-10 w-full min-w-0 bg-transparent text-sm outline-none"
                placeholder={ur ? 'تمام اقسام میں تلاش کریں' : 'Search every category'}
                aria-label={ur ? 'تمام اقسام میں تلاش' : 'Search every category'}
              />
            </label>
            <button
              type="button"
              onClick={close}
              aria-label={ur ? 'اقسام بند کریں' : 'Close categories'}
              className="grid h-11 w-11 place-items-center rounded-xl border border-border hover:bg-muted"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          {needle ? (
            <>
              <p role="status" className="mb-4 text-sm text-muted-foreground">
                {matches.length} {ur ? 'نتائج' : 'matches'}
              </p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {matches.slice(0, shown).map((n) => (
                  <Link
                    key={n.id}
                    href={context.href(categoryBrowseHref(n.id))}
                    className="rounded-xl border border-border bg-card p-3 hover:border-brand/50"
                  >
                    <span className="text-sm font-semibold">{label(n)}</span>
                    <span className="mt-1 block text-xs text-muted-foreground">
                      {categoryPath(n.id).slice(0, -1).map(label).join(' / ')}
                    </span>
                  </Link>
                ))}
              </div>
              {!matches.length && (
                <p className="py-10 text-center text-sm">
                  {ur
                    ? 'کوئی قسم نہیں ملی، دوسرے الفاظ آزمائیں۔'
                    : 'No matching category. Try another product or service name.'}
                </p>
              )}
              {matches.length > shown && (
                <button
                  type="button"
                  onClick={() => setShown((v) => v + 60)}
                  className="mt-4 rounded-lg border border-border px-4 py-2 text-sm text-brand"
                >
                  {ur ? 'مزید دکھائیں' : 'Show more results'}
                </button>
              )}
            </>
          ) : (
            <>
              {selected && (
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="mb-4 inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-brand"
                >
                  <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
                  {ur ? 'تمام اقسام پر واپس' : 'Back to all categories'}
                </button>
              )}
              <div
                className={
                  selected ? 'grid gap-5' : 'grid gap-x-7 gap-y-6 sm:grid-cols-2 lg:grid-cols-4'
                }
              >
                {groups.map((n) => (
                  <div key={n.id} className="min-w-0">
                    <div className="mb-2 flex items-center gap-2.5 border-b border-border pb-2">
                      <Image
                        src={`/images/categories/${n.id}.webp`}
                        width={40}
                        height={40}
                        sizes="40px"
                        alt=""
                        className="h-10 w-10 shrink-0 rounded-xl bg-background object-contain"
                      />
                      <Link
                        href={context.href(categoryBrowseHref(n.id))}
                        className="text-sm font-bold hover:text-brand"
                      >
                        {label(n)}
                      </Link>
                    </div>
                    <ul
                      className={
                        selected
                          ? 'grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-4'
                          : 'space-y-0.5'
                      }
                    >
                      {categoryChildren(n.id).map((c) => (
                        <li key={c.id}>
                          <Link
                            href={context.href(categoryBrowseHref(c.id))}
                            className="block rounded-md px-1 py-1.5 text-sm hover:bg-brand/10 hover:text-brand"
                          >
                            {label(c)}
                          </Link>
                          {categoryChildren(c.id).length > 0 && (
                            <details className="ms-1 border-s border-border ps-2 text-xs text-muted-foreground">
                              <summary className="cursor-pointer rounded-md py-1.5 hover:text-brand">
                                {ur ? 'مزید اقسام' : 'Explore types'} (
                                {categoryChildren(c.id).length})
                              </summary>
                              <ul className="space-y-1 pb-2">
                                {categoryChildren(c.id).map((child) => (
                                  <li key={child.id}>
                                    <Link
                                      className="block rounded-md px-1 py-1.5 hover:bg-muted hover:text-brand"
                                      href={context.href(categoryBrowseHref(child.id))}
                                    >
                                      {label(child)}
                                    </Link>
                                  </li>
                                ))}
                              </ul>
                            </details>
                          )}
                        </li>
                      ))}
                    </ul>
                    {!selected && (
                      <button
                        type="button"
                        onClick={() => setSelected(n.id)}
                        className="mt-2 min-h-9 text-xs font-semibold text-brand hover:underline"
                      >
                        {ur ? 'اس قسم کو کھولیں' : 'Explore this category'} {ur ? '←' : '→'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      )}
    </div>
  );
}
