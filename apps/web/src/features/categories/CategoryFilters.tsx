/** Categoryfilters module; defines parseFacets, CategoryFilters. */
'use client';
import { useEffect, useState } from 'react';
import { useLocale } from 'next-intl';
import {
  categoryChildren,
  categoryPath,
  categoryFields,
  categoryNode,
  categoryOptionLabel,
  productOptions,
  type CategoryField,
} from '@trustlens/constants';
const FILTER_KEYS = new Set([
  'brand',
  'model',
  'make',
  'year',
  'mileage',
  'fuel',
  'transmission',
  'engine',
  'ram',
  'storage',
  'pta',
  'area',
  'area_unit',
  'bedrooms',
  'bathrooms',
  'furnished',
  'rent_period',
  'material',
  'size',
  'product_type',
  'seal',
  'species',
  'breed',
  'employment',
  'work_mode',
  'delivery_mode',
  'service_type',
  'compatible_model',
  'accessory_type',
  'gender',
  'size_system',
  'connectivity',
  'capacity',
]);
export function parseFacets(raw: string | null): Record<string, unknown> {
  try {
    const v: unknown = JSON.parse(raw ?? '{}');
    return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}
export function CategoryFilters({
  nodeId,
  facets,
  onNavigate,
}: {
  nodeId: string | null;
  facets: Record<string, unknown>;
  onNavigate: (next: Record<string, string | null>) => void;
}) {
  const ur = useLocale() === 'ur';
  const path = categoryPath(nodeId);
  const node = categoryNode(nodeId);
  // Broad groups use a generic posting schema, not meaningful phone/car filters.
  // Ask for a subcategory instead of showing Material/Size for all Mobiles.
  const fields =
    node?.schema === 'general' ? [] : categoryFields(nodeId).filter((f) => FILTER_KEYS.has(f.key));
  const [values, setValues] = useState<Record<string, unknown>>(facets);
  const [error, setError] = useState('');
  const signature = JSON.stringify(facets);
  useEffect(() => {
    setValues(parseFacets(signature));
    setError('');
  }, [signature, nodeId]);
  function set(key: string, value: unknown) {
    setValues((v) => ({
      ...v,
      [key]: value,
      ...(['brand', 'make'].includes(key) ? { model: '' } : {}),
    }));
    setError('');
  }
  function apply() {
    const clean: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(values)) {
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        const range = value as { min?: string; max?: string };
        const min = range.min !== undefined && range.min !== '' ? Number(range.min) : undefined;
        const max = range.max !== undefined && range.max !== '' ? Number(range.max) : undefined;
        if (
          (min !== undefined && (!Number.isFinite(min) || min < 0)) ||
          (max !== undefined && (!Number.isFinite(max) || max < 0)) ||
          (min !== undefined && max !== undefined && min > max)
        ) {
          setError(
            ur
              ? 'کم سے کم اور زیادہ سے زیادہ کی حد درست کریں۔'
              : 'Check minimum and maximum ranges.',
          );
          return;
        }
        if (min !== undefined || max !== undefined)
          clean[key] = {
            ...(min !== undefined ? { min } : {}),
            ...(max !== undefined ? { max } : {}),
          };
      } else if (typeof value === 'string' && value.trim()) clean[key] = value.trim();
      else if (typeof value === 'number') clean[key] = value;
    }
    onNavigate({ facets: Object.keys(clean).length ? JSON.stringify(clean) : null, page: null });
  }
  const input = 'h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm';
  function fieldInput(field: CategoryField) {
    const value = values[field.key];
    if (field.type === 'number') {
      const v =
        value && typeof value === 'object'
          ? (value as { min?: string | number; max?: string | number })
          : {};
      return (
        <div className="grid grid-cols-2 gap-2">
          <input
            className={input}
            aria-label={`${ur ? field.labelUr : field.label} ${ur ? 'کم سے کم' : 'minimum'}`}
            inputMode="decimal"
            value={v.min ?? ''}
            placeholder={ur ? 'کم سے کم' : 'Min'}
            onChange={(e) => set(field.key, { ...v, min: e.target.value })}
          />
          <input
            className={input}
            aria-label={`${ur ? field.labelUr : field.label} ${ur ? 'زیادہ سے زیادہ' : 'maximum'}`}
            inputMode="decimal"
            value={v.max ?? ''}
            placeholder={ur ? 'زیادہ سے زیادہ' : 'Max'}
            onChange={(e) => set(field.key, { ...v, max: e.target.value })}
          />
        </div>
      );
    }
    if (field.type === 'select')
      return (
        <select
          className={input}
          aria-label={ur ? field.labelUr : field.label}
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => set(field.key, e.target.value)}
        >
          <option value="">{ur ? 'کوئی بھی' : 'Any'}</option>
          {field.options?.map((o) => (
            <option key={o} value={o}>
              {categoryOptionLabel(o, ur)}
            </option>
          ))}
        </select>
      );
    const choices = nodeId
      ? productOptions(
          nodeId,
          field.key,
          typeof (values.make ?? values.brand) === 'string'
            ? ((values.make ?? values.brand) as string)
            : '',
        )
      : [];
    return (
      <>
        <input
          list={`filter-${field.key}-options`}
          className={input}
          aria-label={ur ? field.labelUr : field.label}
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => set(field.key, e.target.value)}
          maxLength={160}
          placeholder={ur ? 'کوئی بھی' : 'Any'}
        />
        <datalist id={`filter-${field.key}-options`}>
          {choices.map((v) => (
            <option key={v} value={v} />
          ))}
        </datalist>
      </>
    );
  }
  return (
    <section
      className="space-y-3 border-b border-border pb-5"
      aria-label="Category-specific filters"
    >
      <h3 className="font-semibold">{ur ? 'قسم اور تفصیلات' : 'Category & specifications'}</h3>
      {[null, ...path.filter((n) => !n.selectable).map((n) => n.id)].map((parent, index) => (
        <label key={parent ?? 'root'} className="block space-y-1 text-xs">
          <span>{index === 0 ? (ur ? 'قسم' : 'Category') : ur ? 'ذیلی قسم' : 'Subcategory'}</span>
          <select
            className={input}
            value={path[index]?.id ?? ''}
            onChange={(e) =>
              onNavigate({
                categoryNodeId: e.target.value || parent,
                category: null,
                facets: null,
                page: null,
              })
            }
          >
            <option value="">{ur ? 'تمام' : 'All'}</option>
            {categoryChildren(parent).map((n) => (
              <option key={n.id} value={n.id}>
                {ur ? n.labelUr : n.label}
              </option>
            ))}
          </select>
        </label>
      ))}
      {node && fields.length === 0 && (
        <p className="text-xs text-muted-foreground">
          {ur
            ? 'متعلقہ تفصیلات کے لیے ذیلی قسم منتخب کریں۔'
            : 'Choose a subcategory for relevant specification filters.'}
        </p>
      )}
      {node && fields.length > 0 && (
        <details open>
          <summary className="cursor-pointer py-2 text-sm font-medium">
            {ur ? node.labelUr : node.label}
          </summary>
          <div className="space-y-3">
            {fields.map((f) => (
              <label key={f.key} className="block space-y-1 text-xs">
                <span>
                  {ur ? f.labelUr : f.label}
                  {f.unit ? ` (${f.unit})` : ''}
                </span>
                {fieldInput(f)}
              </label>
            ))}
          </div>
          {fields.length > 0 && (
            <button
              type="button"
              onClick={apply}
              className="mt-4 w-full rounded-lg border border-brand/40 px-3 py-2 text-sm font-semibold text-brand"
            >
              {ur ? 'تفصیلات کے فلٹر لگائیں' : 'Apply specification filters'}
            </button>
          )}
        </details>
      )}
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </section>
  );
}
