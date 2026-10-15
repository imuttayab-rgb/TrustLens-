import { MARKETPLACE_NODES, MARKETPLACE_ROOTS, categoryPath } from '@trustlens/constants';

/** Presentation groups only: category IDs, fields and URLs remain catalogue-owned. */
export const ATLAS_SECTIONS = [
  {
    id: 'technology',
    label: 'Technology',
    labelUr: 'ٹیکنالوجی',
    roots: ['mobiles', 'electronics-appliances', 'books-sports-hobbies'],
  },
  {
    id: 'transport',
    label: 'Transport',
    labelUr: 'سواری',
    roots: ['vehicles', 'bikes'],
  },
  {
    id: 'property',
    label: 'Property',
    labelUr: 'پراپرٹی',
    roots: ['property-sale', 'property-rent'],
  },
  {
    id: 'living',
    label: 'Everyday Living',
    labelUr: 'روزمرہ زندگی',
    roots: ['furniture', 'fashion-beauty', 'kids', 'animals'],
  },
  {
    id: 'work',
    label: 'Work & More',
    labelUr: 'کام اور دیگر',
    roots: ['business-industrial-agriculture', 'services', 'jobs'],
  },
] as const;
export type AtlasSectionId = (typeof ATLAS_SECTIONS)[number]['id'];
const assignedRoots = new Set<string>(ATLAS_SECTIONS.flatMap((s) => [...s.roots]));
export const ATLAS_GROUPS = ATLAS_SECTIONS.map((section) => ({
  ...section,
  categories: [
    ...section.roots.flatMap((id) => MARKETPLACE_ROOTS.filter((n) => n.id === id)),
    // Future catalogue roots remain reachable until they receive their own grouping.
    ...(section.id === 'work' ? MARKETPLACE_ROOTS.filter((n) => !assignedRoots.has(n.id)) : []),
  ],
}));
const children = new Map<string, typeof MARKETPLACE_NODES>();
for (const node of MARKETPLACE_NODES) {
  if (!node.parentId) continue;
  const siblings = children.get(node.parentId) ?? [];
  siblings.push(node);
  children.set(node.parentId, siblings);
}
export const atlasChildren = (id: string) => children.get(id) ?? [];

// Approved five-column preview budgets. The full catalogue stays in the directory.
// Shorter thematic columns expose more useful links; no unrelated filler or fake inventory.
export const ATLAS_PREVIEW_LIMITS: Readonly<Record<string, number>> = {
  mobiles: 5,
  'electronics-appliances': 6,
  'books-sports-hobbies': 4,
  vehicles: 11,
  bikes: 7,
  'property-sale': 5,
  'property-rent': 8,
  furniture: 4,
  'fashion-beauty': 4,
  kids: 3,
  animals: 3,
  'business-industrial-agriculture': 5,
  services: 4,
  jobs: 5,
};
// Curated shortcuts, not a popularity claim.
const previewOrder: Record<string, readonly string[]> = {
  'electronics-appliances': [
    'laptops',
    'computers-accessories',
    'televisions-accessories',
    'cameras-accessories',
    'games-entertainment',
    'refrigerators-freezers',
  ],
  vehicles: [
    'cars',
    'cars-on-installments',
    'car-care',
    'cars-accessories',
    'spare-parts',
    'buses-vans-trucks',
    'tractors-trailers',
    'oil-lubricants',
    'rickshaw-chingchi',
    'boats',
    'other-vehicles',
  ],
  bikes: [
    'motorcycles',
    'bicycles',
    'scooters',
    'spare-parts',
    'bikes-accessories',
    'atv-quads',
    'bike-care',
  ],
  furniture: ['sofa-chairs', 'beds-wardrobes', 'tables-dining', 'lighting', 'home-decoration'],
  'fashion-beauty': ['clothes', 'footwear', 'cosmetics', 'skincare', 'makeup'],
  kids: ['toys', 'baby-gear', 'kids-accessories', 'kids-vehicles', 'bath-diapers'],
  animals: ['cats', 'dogs', 'pet-food-accessories', 'parrots', 'livestock'],
  services: [
    'home-office-repair',
    'movers-packers',
    'web-development',
    'tuitions-academies',
    'catering-restaurant',
  ],
  jobs: ['accounting-finance', 'customer-service', 'it-networking', 'sales', 'part-time'],
  'business-industrial-agriculture': [
    'business-for-sale',
    'agriculture',
    'construction-heavy-machinery',
    'medical-pharma',
    'trade-industrial-machinery',
  ],
  'books-sports-hobbies': [
    'books-magazines',
    'sports-equipment',
    'gym-fitness',
    'arts-crafts',
    'musical-instruments',
  ],
};
export function atlasPreview(id: string) {
  const nodes = atlasChildren(id);
  const preferred = (previewOrder[id] ?? []).flatMap((slug) =>
    nodes.filter((n) => n.id === id + '/' + slug),
  );
  const seen = new Set(preferred.map((n) => n.id));
  return [...preferred, ...nodes.filter((n) => !seen.has(n.id))].slice(
    0,
    ATLAS_PREVIEW_LIMITS[id] ?? 5,
  );
}
const normalize = (value: string) =>
  value.normalize('NFKC').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
const searchIndex = MARKETPLACE_NODES.map((node) => ({
  node,
  path: categoryPath(node.id),
  text: normalize(
    categoryPath(node.id)
      .map((n) => n.label + ' ' + n.labelUr)
      .join(' '),
  ),
}));
export function searchAtlas(query: string) {
  const terms = normalize(query).split(' ').filter(Boolean);
  return terms.length
    ? searchIndex.filter((row) => terms.every((term) => row.text.includes(term)))
    : [];
}
