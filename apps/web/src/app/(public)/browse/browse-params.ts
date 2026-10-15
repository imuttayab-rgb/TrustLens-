// The URL is the source of truth for applied marketplace filters. Header links,
// sidebar category buttons, filter chips, and browser history all read it.
export function priceFromInput(value: string | null): number | null {
  const text = value?.trim() ?? '';
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(text)) return null;
  const price = Number(text.replace(/,/g, ''));
  return Number.isFinite(price) && price <= Number.MAX_SAFE_INTEGER ? price : null;
}

export function priceRangeError(min: string | null, max: string | null): string | null {
  const low = priceFromInput(min);
  const high = priceFromInput(max);
  if ((min?.trim() && low === null) || (max?.trim() && high === null)) {
    return 'Enter a valid price, such as 40000 or 40,000. Negative prices are not allowed.';
  }
  if (low !== null && high !== null && low > high) {
    return 'Maximum price must be equal to or higher than minimum price.';
  }
  return null;
}

export function pageFromParam(value: string | null): number {
  const page = Number(value);
  return Number.isSafeInteger(page) && page >= 1 && page <= Math.floor(Number.MAX_SAFE_INTEGER / 24)
    ? page
    : 1;
}

export function nextBrowseHref(
  search: string,
  updates: Record<string, string | null | undefined>,
  resetPage = true,
): string {
  const params = new URLSearchParams(search);
  for (const [key, value] of Object.entries(updates)) {
    if (value === undefined) continue;
    if (value) params.set(key, value);
    else params.delete(key);
  }
  if (resetPage) params.delete('page');
  return `/browse${params.toString() ? `?${params.toString()}` : ''}`;
}
