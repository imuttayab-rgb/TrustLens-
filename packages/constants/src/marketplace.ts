/** Marketplace module; defines CategoryNode, CategoryField, MARKETPLACE_NODES, MARKETPLACE_ROOTS, MARKETPLACE_SCHEMA_VERSION, categoryNode. */
import data from './marketplace-data.json';
import options from './product-options.json';

export interface CategoryNode {
  id: string;
  parentId: string | null;
  label: string;
  labelUr: string;
  legacyCategory: string;
  schema: string;
  policy: 'physical' | 'service' | 'job' | 'transfer';
  conditionRequired: boolean;
  priceLabel: string;
  selectable: boolean;
  reference: string;
}
export interface CategoryField {
  key: string;
  label: string;
  labelUr: string;
  type: 'text' | 'number' | 'select' | 'date';
  required: boolean;
  unit?: string;
  options?: string[];
  min?: number;
  max?: number;
}
export const MARKETPLACE_NODES = data.nodes as CategoryNode[];
export const MARKETPLACE_ROOTS = MARKETPLACE_NODES.filter((n) => !n.parentId);
const byId = new Map(MARKETPLACE_NODES.map((n) => [n.id, n]));
export const MARKETPLACE_SCHEMA_VERSION = data.version;
export function categoryNode(id: string | null | undefined) {
  return id ? byId.get(id) : undefined;
}
export function categoryChildren(id: string | null) {
  return MARKETPLACE_NODES.filter((n) => n.parentId === id);
}
export function categoryPath(id: string | null | undefined): CategoryNode[] {
  const node = categoryNode(id);
  return node ? [...categoryPath(node.parentId), node] : [];
}
export function categoryLabel(id: string | null | undefined, ur = false): string {
  const node = categoryNode(id);
  return node ? (ur ? node.labelUr : node.label) : '';
}
export function categoryFields(id: string | null | undefined): CategoryField[] {
  const node = categoryNode(id);
  return node
    ? ((data.schemas as unknown as Record<string, CategoryField[]>)[node.schema] ?? [])
    : [];
}
export function categoryGuidance(id: string | null | undefined, ur = false): string {
  const node = categoryNode(id);
  if (ur && node) return (data.guidanceUr as Record<string, string>)[node.schema] ?? '';
  return node ? ((data.guidance as Record<string, string>)[node.schema] ?? '') : '';
}
export function categoryBrowseHref(id: string): string {
  return `/browse?categoryNodeId=${encodeURIComponent(id)}`;
}

export const BROWSE_LOCATION_KEYS = ['city', 'area', 'lat', 'lng', 'radius'] as const;
export function browseLocation(params: { get: (key: string) => string | null }) {
  const number = (key: string) => {
    const raw = params.get(key);
    return raw !== null && raw.trim() && Number.isFinite(Number(raw)) ? Number(raw) : null;
  };
  const city = params.get('city')?.trim().slice(0, 100) || null;
  const lat = number('lat'),
    lng = number('lng'),
    radius = number('radius');
  const near =
    lat !== null &&
    lng !== null &&
    Math.abs(lat) <= 90 &&
    Math.abs(lng) <= 180 &&
    radius !== null &&
    radius > 0 &&
    radius <= 500;
  return {
    city,
    area: city ? params.get('area')?.trim().slice(0, 100) || null : null,
    lat: near ? lat : null,
    lng: near ? lng : null,
    radius: near ? radius : null,
  };
}
export function withBrowseLocation(path: string, params: { get: (key: string) => string | null }) {
  // Never copy a login token, arbitrary query parameter or external redirect.
  if (!path.startsWith('/') || path.startsWith('//')) return path;
  const [withoutHash, hash] = path.split('#');
  const [base, rest = ''] = (withoutHash ?? path).split('?');
  const next = new URLSearchParams(rest);
  const location = browseLocation(params);
  const changesCity = next.has('city') && next.get('city') !== location.city;
  for (const key of BROWSE_LOCATION_KEYS) {
    if (changesCity && key !== 'city') continue;
    if (!next.has(key) && location[key] !== null) next.set(key, String(location[key]));
  }
  return `${base}${next.size ? `?${next}` : ''}${hash ? `#${hash}` : ''}`;
}
export function specKey(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]/g, '');
}
/** Read one confirmed card. This never guesses a variant from a product name. */
export function categorySpec(
  field: CategoryField,
  specs: { key: string; value: string }[],
): string {
  const row = specs.find((s) =>
    [specKey(field.label), specKey(field.key)].includes(specKey(s.key)),
  );
  return row?.value ?? '';
}
export function categoryFieldErrors(
  id: string | null | undefined,
  specs: { key: string; value: string }[],
  required = false,
): string[] {
  const errors: string[] = [];
  for (const field of categoryFields(id)) {
    const raw = categorySpec(field, specs).trim();
    if (!raw) {
      if (required && field.required) errors.push(`Enter ${field.label}.`);
      continue;
    }
    if (field.type === 'number') {
      const escaped = field.unit?.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const match = raw.match(
        new RegExp(`^\\s*(\\d+(?:\\.\\d+)?)\\s*${escaped ? `(?:${escaped})?` : ''}\\s*$`, 'i'),
      );
      const value = match ? Number(match[1]) : NaN;
      if (!Number.isFinite(value) || value < (field.min ?? 0) || value > (field.max ?? 100000000))
        errors.push(`Check ${field.label}${field.unit ? ` (${field.unit})` : ''}.`);
    } else if (
      field.type === 'select' &&
      !field.options?.some((v) => v.toLowerCase() === raw.toLowerCase())
    )
      errors.push(`Choose a listed value for ${field.label}.`);
    else if (
      field.type === 'date' &&
      (!/^\d{4}-\d{2}-\d{2}$/.test(raw) ||
        !Number.isFinite(Date.parse(raw)) ||
        new Date(raw).toISOString().slice(0, 10) !== raw)
    )
      errors.push(`Use a valid YYYY-MM-DD date for ${field.label}.`);
  }
  return errors;
}

export function categoryOptionLabel(value: string, ur = false) {
  return ur ? ((data.optionLabelsUr as Record<string, string>)[value] ?? value) : value;
}
/** Only confirmed typed values appear on inventory cards; blanks produce no claim. */
export function listingSpecSummary(
  nodeId: string | null | undefined,
  values: Record<string, string | number> = {},
  ur = false,
): string[] {
  const node = categoryNode(nodeId);
  const keys: Record<string, string[]> = {
    vehicle: ['year', 'mileage', 'fuel', 'transmission'],
    phone: ['ram', 'storage', 'pta'],
    tablet: ['storage', 'connectivity'],
    computer: ['processor', 'ram', 'storage'],
    property: ['bedrooms', 'bathrooms', 'area', 'area_unit'],
    rent: ['bedrooms', 'bathrooms', 'area', 'area_unit'],
    land: ['area', 'area_unit'],
    'land-rent': ['area', 'area_unit'],
    cosmetics: ['quantity', 'quantity_unit', 'seal'],
    fragrance: ['volume', 'seal'],
    job: ['employment', 'work_mode'],
    service: ['service_type', 'delivery_mode'],
    accessory: ['accessory_type', 'compatible_model'],
    part: ['part_type', 'compatible_model'],
  };
  const fields = categoryFields(nodeId);
  const chosen = node
    ? (keys[node.schema] ??
      fields
        .filter(
          (f) => !['faults', 'included', 'authenticity', 'expiry', 'ingredients'].includes(f.key),
        )
        .map((f) => f.key)
        .slice(0, 3))
    : [];
  const result: string[] = [];
  for (const key of chosen) {
    const raw = values[key];
    if (raw === undefined || raw === null || raw === '') continue;
    const field = fields.find((f) => f.key === key);
    if (key === 'area_unit' || key === 'quantity_unit') continue;
    const number =
      typeof raw === 'number' ? raw.toLocaleString(ur ? 'ur-PK' : 'en-PK') : String(raw);
    if (key === 'area' || key === 'quantity') {
      const unit = values[`${key}_unit`];
      if (unit) result.push(`${number} ${categoryOptionLabel(String(unit), ur)}`);
      continue;
    }
    result.push(
      field?.type === 'number'
        ? `${number}${field.unit ? ` ${field.unit}` : ''}${['ram', 'storage', 'bedrooms', 'bathrooms'].includes(key) ? ` ${ur ? field.labelUr : field.label}` : ''}`
        : categoryOptionLabel(String(raw), ur),
    );
  }
  return result.slice(0, 4);
}

/** Search vocabulary is a suggestion, never proof of a specification or stock. */
export function productOptions(nodeId: string, field: string, brand = ''): string[] {
  const node = categoryNode(nodeId);
  if (!node) return [];
  const groups: Record<string, string> = {
    phone: 'mobiles',
    tablet: 'tablets',
    computer: 'computers',
    vehicle: nodeId.startsWith('bikes/') ? 'bike' : 'car',
    appliance: 'home-appliances',
    tv: 'tv',
    gaming: 'gaming',
    camera: 'camera',
    wearable: 'wearable',
    audio: 'audio',
  };
  const group = groups[node.schema];
  const entries = group ? ((options as Record<string, Record<string, string[]>>)[group] ?? {}) : {};
  if (field === 'brand' || field === 'make') return Object.keys(entries).sort();
  if (field === 'model') {
    const key = Object.keys(entries).find((k) => k.toLowerCase() === brand.trim().toLowerCase());
    return key ? (entries[key] ?? []) : [];
  }
  return [];
}
