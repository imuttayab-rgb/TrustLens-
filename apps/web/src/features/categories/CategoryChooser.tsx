/** Categorychooser module; defines CategoryChooser. */
'use client';
import { useState } from 'react';
import { useLocale } from 'next-intl';
import Image from 'next/image';
import {
  categoryChildren,
  categoryPath,
  MARKETPLACE_NODES,
  type CategoryNode,
} from '@trustlens/constants';
import { ChevronRight, Search } from 'lucide-react';

/** Category first; the established four-step editor remains unchanged. */
export function CategoryChooser({
  onSelect,
  onCancel,
}: {
  onSelect: (node: CategoryNode) => void;
  onCancel?: () => void;
}) {
  const ur = useLocale() === 'ur';
  const [parent, setParent] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [shown, setShown] = useState(60);
  const path = categoryPath(parent);
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
  const label = (n: CategoryNode) => (ur ? n.labelUr : n.label);
  const select = (n: CategoryNode) => (n.selectable ? onSelect(n) : setParent(n.id));
  const choice = (n: CategoryNode, compact = false) => (
    <button
      key={n.id}
      type="button"
      aria-pressed={!n.selectable && path.some((p) => p.id === n.id)}
      onClick={() => select(n)}
      className={`flex w-full items-center justify-between gap-3 rounded-xl border p-3 text-start text-sm focus-visible:ring-2 focus-visible:ring-ring ${path.some((p) => p.id === n.id) ? 'border-brand bg-brand/10' : 'border-border bg-background hover:border-brand/50'}`}
    >
      {!compact && !n.parentId && (
        <Image
          src={`/images/categories/${n.id}.webp`}
          width={48}
          height={48}
          alt=""
          className="h-12 w-12 object-contain"
        />
      )}
      <span className="min-w-0 flex-1">
        <span className="font-semibold">{label(n)}</span>
        {needle && (
          <span className="mt-1 block text-xs text-muted-foreground">
            {categoryPath(n.id).slice(0, -1).map(label).join(' / ')}
          </span>
        )}
      </span>
      <ChevronRight className="h-4 w-4 shrink-0 text-brand rtl:rotate-180" aria-hidden="true" />
    </button>
  );
  return (
    <section
      className="mx-auto max-w-6xl rounded-2xl border border-border bg-card p-5 sm:p-8"
      aria-labelledby="choose-category-title"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm text-brand">{ur ? 'اشتہار دیں' : 'Post an Ad'}</p>
          <h1 id="choose-category-title" className="mt-1 text-2xl font-semibold">
            {ur ? 'آپ کیا پیش کر رہے ہیں؟' : 'What are you listing?'}
          </h1>
        </div>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-border px-4 py-2 text-sm"
          >
            {ur ? 'مسودے پر واپس' : 'Back to your draft'}
          </button>
        )}
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        {ur
          ? 'قسم منتخب کرنے کے بعد: تفصیلات، تصاویر اور ویڈیو، مقام، پیش نظارہ اور اشاعت۔'
          : 'Choose a category, then continue: Details, Photos & Video, Location, Preview & Publish.'}
      </p>
      <label className="mt-6 flex items-center gap-2 rounded-xl border border-input px-3">
        <Search className="h-4 w-4" aria-hidden="true" />
        <input
          autoComplete="off"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setShown(60);
          }}
          placeholder={
            ur ? 'قسم یا چیز کا نام تلاش کریں' : 'Search categories, e.g. skincare or spare parts'
          }
          className="h-12 w-full bg-transparent text-sm outline-none"
          aria-label={ur ? 'قسم تلاش کریں' : 'Search categories'}
        />
      </label>
      <nav
        className="my-5 flex flex-wrap items-center gap-2 text-sm"
        aria-label={ur ? 'منتخب قسم' : 'Category path'}
      >
        <button
          type="button"
          onClick={() => {
            setParent(null);
            setQuery('');
          }}
          className="font-medium text-brand"
        >
          {ur ? 'تمام اقسام' : 'All categories'}
        </button>
        {path.map((n) => (
          <span key={n.id} className="inline-flex items-center gap-2">
            <ChevronRight className="h-3 w-3 rtl:rotate-180" />
            <button
              type="button"
              onClick={() => {
                setParent(n.id);
                setQuery('');
              }}
            >
              {label(n)}
            </button>
          </span>
        ))}
      </nav>
      {needle ? (
        <>
          <p role="status" className="mb-3 text-xs text-muted-foreground">
            {matches.length} {ur ? 'نتائج' : 'matches'}
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {matches.slice(0, shown).map((n) => choice(n))}
          </div>
          {!matches.length && (
            <p className="py-8 text-center" role="status">
              {ur
                ? 'کوئی قسم نہیں ملی۔ دوسرے الفاظ آزمائیں۔'
                : 'No matching category. Try a broader product or service name.'}
            </p>
          )}
          {matches.length > shown && (
            <button
              type="button"
              onClick={() => setShown((v) => v + 60)}
              className="mt-4 rounded-lg border border-border px-4 py-2 text-brand"
            >
              {ur ? 'مزید دکھائیں' : 'Show more matches'}
            </button>
          )}
        </>
      ) : !parent ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {categoryChildren(null).map((n) => choice(n))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {[null, ...path.map((n) => n.id)].map((p, i) => (
            <section key={p ?? 'root'} className="min-w-0 rounded-xl border border-border p-3">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {i === 0
                  ? ur
                    ? 'قسم'
                    : 'Category'
                  : i === 1
                    ? ur
                      ? 'ذیلی قسم'
                      : 'Subcategory'
                    : ur
                      ? 'قسم منتخب کریں'
                      : 'Choose a type'}
              </h2>
              <div className="space-y-2 md:max-h-[440px] md:overflow-y-auto md:pe-1">
                {categoryChildren(p).map((n) => choice(n, true))}
              </div>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}
