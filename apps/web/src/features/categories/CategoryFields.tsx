/** Categoryfields module; defines CategoryFields, isCategoryField. */
'use client';
import { useEffect, useId, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  categoryFields,
  categorySpec,
  specKey,
  categoryOptionLabel,
  productOptions,
  type CategoryField,
} from '@trustlens/constants';
import { useLocale } from 'next-intl';
import { profileRequest } from '@/features/profile';

export function CategoryFields({
  nodeId,
  specs,
  onChange,
  disabled,
}: {
  nodeId: string;
  specs: { key: string; value: string }[];
  onChange: (field: CategoryField, value: string) => void;
  disabled: boolean;
}) {
  const fields = categoryFields(nodeId);
  const brandField = fields.find((f) => f.key === 'make' || f.key === 'brand');
  const brand = brandField ? categorySpec(brandField, specs) : '';
  return (
    <div className="my-4 grid gap-4 sm:grid-cols-2">
      {fields.map((field) => (
        <CategoryFieldInput
          key={`${nodeId}:${field.key}`}
          {...{ nodeId, field, brand, onChange, disabled }}
          value={categorySpec(field, specs)}
        />
      ))}
    </div>
  );
}
function CategoryFieldInput({
  nodeId,
  field,
  brand,
  value,
  onChange,
  disabled,
}: {
  nodeId: string;
  field: CategoryField;
  brand: string;
  value: string;
  onChange: (field: CategoryField, value: string) => void;
  disabled: boolean;
}) {
  const ur = useLocale() === 'ur';
  const id = useId();
  const [focused, setFocused] = useState(false);
  const [query, setQuery] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setQuery(value), 300);
    return () => clearTimeout(timer);
  }, [value]);
  const suggested = ['brand', 'make', 'model', 'compatible_model'].includes(field.key);
  const choices = productOptions(nodeId, field.key, brand);
  const live = useQuery<string[]>({
    queryKey: ['category-options', nodeId, field.key, brand, query],
    enabled: focused && suggested,
    staleTime: 300000,
    retry: false,
    queryFn: ({ signal }) =>
      profileRequest<string[]>(
        `/public/catalogue-options?${new URLSearchParams({ categoryNodeId: nodeId, field: field.key, parentValue: field.key === 'model' ? brand : '', q: query.slice(0, 80) })}`,
        { signal },
      ),
  });
  const options = [...new Set([...choices, ...(live.data ?? [])])];
  const invalidSelect = field.type === 'select' && value && !field.options?.includes(value);
  const common = {
    id,
    disabled,
    className:
      'h-10 w-full min-w-0 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring',
    value,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      onChange(field, e.target.value),
  };
  return (
    <label htmlFor={id} className="space-y-1 text-sm">
      <span className="font-medium">
        {ur ? field.labelUr : field.label}
        {field.unit ? ` (${field.unit})` : ''}
        {field.required ? ' *' : ''}
      </span>
      {field.type === 'select' ? (
        <select {...common}>
          <option value="">{ur ? 'معلوم ہو تو منتخب کریں' : 'Choose if known'}</option>
          {invalidSelect && (
            <option value={value}>
              {value} — {ur ? 'تصدیق کریں' : 'review detected value'}
            </option>
          )}
          {field.options?.map((o) => (
            <option key={o} value={o}>
              {categoryOptionLabel(o, ur)}
            </option>
          ))}
        </select>
      ) : (
        <>
          <input
            {...common}
            type={field.type === 'date' ? 'date' : 'text'}
            inputMode={field.type === 'number' ? 'decimal' : undefined}
            maxLength={80}
            autoComplete="off"
            list={suggested ? `${id}-choices` : undefined}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder={ur ? 'نامعلوم ہو تو خالی چھوڑیں' : 'Leave blank if unknown'}
          />
          {suggested && (
            <datalist id={`${id}-choices`}>
              {options.map((o) => (
                <option key={o} value={o} />
              ))}
            </datalist>
          )}
        </>
      )}
      {suggested && (
        <span className="block text-[11px] font-normal text-muted-foreground">
          {ur
            ? 'فہرست میں نہ ہو تو خود لکھیں۔ انتخاب سے کوئی اور تفصیل خود نہیں بھرتی۔'
            : 'Choose a suggestion or type your own. Other details stay yours to confirm.'}
        </span>
      )}
    </label>
  );
}
export function isCategoryField(nodeId: string, spec: { key: string }) {
  return categoryFields(nodeId).some((f) =>
    [specKey(f.label), specKey(f.key)].includes(specKey(spec.key)),
  );
}
