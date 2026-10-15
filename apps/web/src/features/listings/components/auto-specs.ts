import { categoryFields, categoryNode } from '@trustlens/constants';
/** Extract only explicit seller facts. No network, product-spec guesses or photo inference. */
export type ProductSpec = { key: string; value: string };
export type SpecInput = {
  title: string;
  category: string;
  categoryNodeId?: string | null;
  description: string;
};
export type Detection = { specs: ProductSpec[]; ambiguous: string[] };

const COMMON: Record<string, string[]> = {
  Brand: ['brand', 'make', 'برانڈ'],
  Model: ['model', 'exact model', 'ماڈل'],
  Colour: ['colour', 'color', 'رنگ'],
  'Condition details': ['condition details', 'faults', 'issues', 'repairs', 'خرابی'],
  'Included accessories': ['included accessories', 'accessories', 'included items'],
  Warranty: ['warranty', 'وارنٹی'],
};
const DEVICE: Record<string, string[]> = {
  RAM: ['ram', 'ریم'],
  Storage: ['storage', 'internal storage', 'rom', 'سٹوریج', 'اسٹوریج'],
  Processor: ['processor', 'cpu', 'پروسیسر'],
  Display: ['display', 'screen size'],
  'Battery capacity': ['battery capacity'],
  'Charging port': ['charging port', 'port'],
};
const CATEGORY: Record<string, Record<string, string[]>> = {
  mobiles: {
    ...DEVICE,
    'PTA status': ['pta', 'pta status', 'پی ٹی اے'],
    'Battery health': ['battery health', 'battery health percentage', 'بیٹری ہیلتھ'],
    'Face ID': ['face id', 'faceid'],
    'True Tone': ['true tone', 'truetone'],
    Screen: ['screen', 'screen condition'],
    Box: ['box', 'باکس'],
    Charger: ['charger', 'چارجر'],
  },
  computers: {
    ...DEVICE,
    Graphics: ['graphics', 'gpu', 'graphics card'],
    'Operating system': ['operating system', 'os'],
    'Battery backup': ['battery backup'],
    Charger: ['charger', 'چارجر'],
  },
  electronics: {
    ...DEVICE,
    Resolution: ['resolution'],
    Connectivity: ['connectivity'],
    Edition: ['edition'],
    'Included controllers': ['included controllers', 'controllers'],
  },
  vehicles: {
    Year: ['year', 'model year'],
    Mileage: ['mileage', 'driven', 'odometer'],
    'Engine capacity': ['engine capacity', 'engine', 'cc'],
    Transmission: ['transmission', 'gearbox'],
    'Fuel type': ['fuel', 'fuel type'],
    'Registration city': ['registration city', 'registered in'],
    Documents: ['documents', 'papers'],
  },
  'vehicle-parts': {
    'Part number': ['part number'],
    Compatibility: ['compatibility', 'compatible models', 'compatible with'],
    Quantity: ['quantity'],
  },
  'home-appliances': {
    Capacity: ['capacity'],
    Type: ['type', 'load type'],
    Power: ['power', 'wattage'],
    Dimensions: ['dimensions'],
    'Energy rating': ['energy rating'],
    'Spin speed': ['spin speed'],
    Motor: ['motor'],
  },
  furniture: {
    Material: ['material'],
    Dimensions: ['dimensions'],
    'Seating capacity': ['seating capacity', 'seats'],
    'Included pieces': ['included pieces', 'pieces'],
  },
  fashion: {
    Size: ['size', 'shoe size'],
    Material: ['material', 'fabric'],
    Fit: ['fit'],
  },
  'books-hobbies': {
    Edition: ['edition'],
    Author: ['author'],
    Language: ['language'],
    ISBN: ['isbn'],
    'Number of pieces': ['number of pieces'],
  },
  animals: {
    Breed: ['breed'],
    Species: ['species'],
    Age: ['age'],
    'Vaccination status': ['vaccination status', 'vaccination'],
  },
  services: {
    'Service scope': ['service scope', 'service'],
    'Service area': ['service area'],
    Experience: ['experience'],
    Availability: ['availability'],
    'Price includes': ['price includes'],
  },
  other: {
    Size: ['size'],
    Capacity: ['capacity'],
    Material: ['material'],
    Dimensions: ['dimensions'],
  },
};
const PROPERTY = {
  'Property type': ['property type'],
  Area: ['area', 'plot size'],
  Bedrooms: ['bedrooms', 'beds'],
  Bathrooms: ['bathrooms', 'baths'],
  Furnished: ['furnished', 'furnishing'],
  'Possession status': ['possession status', 'possession'],
};
CATEGORY['property-sale'] = PROPERTY;
CATEGORY['property-rent'] = PROPERTY;

const aliases = new Map<string, string>();
for (const fields of [COMMON, ...Object.values(CATEGORY)]) {
  for (const [key, names] of Object.entries(fields)) {
    for (const name of [key, ...names]) aliases.set(name.toLowerCase(), key.toLowerCase());
  }
}
export function specKey(key: string): string {
  const normal = key.trim().toLowerCase().replace(/\s+/g, ' ');
  return aliases.get(normal) ?? normal;
}
export function sameValue(a: string, b: string): boolean {
  return a.toLowerCase().replace(/[\s-]+/g, '') === b.toLowerCase().replace(/[\s-]+/g, '');
}

function clean(value: string): string {
  return value.trim().replace(/\s+/g, ' ');
}
function normalise(text: string): string {
  return text
    .normalize('NFKC')
    .replace(/[۰-۹٠-٩]/g, (n) => String(n.charCodeAt(0) - (n >= '۰' ? 0x6f0 : 0x660)));
}
function escaped(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function detectSpecs(original: SpecInput): Detection {
  const schema = categoryNode(original.categoryNodeId)?.schema;
  const input =
    schema &&
    [
      'accessory',
      'wearable',
      'landline',
      'mobile-number',
      'audio',
      'controller',
      'power-equipment',
      'tool',
      'pet-food',
      'pet-accessory',
      'cosmetics',
      'footwear',
      'craft',
      'textile',
      'lighting',
      'kitchenware',
      'farm-produce',
      'agri-supply',
      'medical-supply',
      'medicine',
      'material',
    ].includes(schema)
      ? { ...original, category: 'other' }
      : original;
  if (!input.category) return { specs: [], ambiguous: [] };
  const text = normalise(input.description.slice(0, 8000));
  const title = normalise(input.title.slice(0, 80));
  const candidates = new Map<string, ProductSpec[]>();
  function add(key: string, raw: string) {
    let value = clean(raw).replace(/[.;]+$/, '');
    if (
      ['RAM', 'Storage', 'Battery capacity'].includes(key) &&
      /^\d+\s*(?:GB|TB|mAh)(?:\s+(?:SSD|HDD|RAM|ROM))?$/i.test(value)
    ) {
      value = value
        .replace(/\s+(?:SSD|HDD|RAM|ROM)$/i, '')
        .replace(/\s+/g, '')
        .replace(/gb|tb/gi, (v) => v.toUpperCase());
    }
    if (key === 'PTA status') {
      if (/^(?:non[ -]?pta|not approved|unapproved|no|nahi|nai)$/i.test(value)) value = 'Non-PTA';
      else if (/^(?:pta approved|approved|yes)$/i.test(value)) value = 'Approved';
    }
    if (['Box', 'Charger'].includes(key)) {
      if (/^(?:no|not included|not available|missing|nahi|nai|نہیں)$/i.test(value))
        value = 'Not included';
      else if (/^(?:yes|available|included|hai|ہے)$/i.test(value)) value = 'Included';
    }
    // Never truncate a fault or turn a question/placeholder into a claim.
    if (!value || value.length > 80 || /[?؟]|^(?:unknown|not sure|tbc|n\/a|نامعلوم)$/i.test(value))
      return;
    const canonical = specKey(key);
    const list = candidates.get(canonical) ?? [];
    if (!list.some((s) => sameValue(s.value, value))) list.push({ key, value });
    candidates.set(canonical, list);
  }
  function matches(key: string, pattern: RegExp, value: (m: RegExpMatchArray) => string) {
    for (const m of text.matchAll(pattern)) {
      const start = m.index ?? 0;
      const before = text.slice(Math.max(0, start - 22), start);
      const after = text.slice(start + m[0].length, start + m[0].length + 22);
      if (
        /(?:not|no|without|nahi|nai|nahin|non[ -]?)\s*$/i.test(before) ||
        /^\s*(?:nahi|nai|nahin|نہیں|not\b|[?؟])/i.test(after)
      )
        continue;
      if (
        key === 'Storage' &&
        /(?:RAM|memory card|SD card|cloud|external)\s*[:=]?\s*$/i.test(before)
      )
        continue;
      add(key, value(m));
    }
  }

  // Explicit, category-allowed Label: value works across every marketplace category.
  // Splitting at every labelled segment prevents swallowing adjacent fields.
  const fields = {
    ...COMMON,
    ...(CATEGORY[input.category] ?? CATEGORY.other),
    ...Object.fromEntries(
      categoryFields(input.categoryNodeId).map((f) => [f.label, [f.key, f.labelUr]]),
    ),
  };
  const labels = new Map<string, string>();
  for (const [key, names] of Object.entries(fields)) {
    for (const name of [key, ...names]) labels.set(name.toLowerCase(), key);
  }
  const names = [...labels.keys()]
    .sort((a, b) => b.length - a.length)
    .map(escaped)
    .join('|');
  const labelled = new RegExp(`(?:^|[\\s,;|•])(${names})\\s*[:=]\\s*`, 'gimu');
  const found = [...text.matchAll(labelled)];
  for (let i = 0; i < found.length; i++) {
    const m = found[i];
    if (!m) continue;
    const from = (m.index ?? 0) + m[0].length;
    const to = found[i + 1]?.index ?? text.length;
    const raw = text.slice(from, to).split(/[,،;\n|•]/)[0] ?? '';
    const key = labels.get((m[1] ?? '').toLowerCase());
    if (key) add(key, raw);
  }

  const devices = ['mobiles', 'computers', 'electronics'].includes(input.category);
  if (devices) {
    matches('RAM', /\b(\d{1,3})\s*GB\s*(?:of\s+)?RAM\b/gi, (m) => `${m[1]}GB`);
    matches('RAM', /(?:\bRAM|ریم)\s*[:=]?\s*(\d{1,3})\s*GB\b/gi, (m) => `${m[1]}GB`);
    matches(
      'Storage',
      /\b(\d{1,4})\s*(GB|TB)\s*(?:internal\s+)?(?:storage|ROM|SSD|HDD)\b/gi,
      (m) => `${m[1]}${m[2]?.toUpperCase()}`,
    );
    matches(
      'Storage',
      /\b(?:storage|ROM|SSD|HDD)\s*[:=]?\s*(\d{1,4})\s*(GB|TB)\b/gi,
      (m) => `${m[1]}${m[2]?.toUpperCase()}`,
    );
    matches(
      'Display',
      /\b(\d{1,2}(?:\.\d)?)\s*(?:inch(?:es)?|["″])(?:\s+(?:display|screen))?/gi,
      (m) => `${m[1]} inches`,
    );
    matches('Battery capacity', /\b(\d{3,5})\s*mAh\b/gi, (m) => `${m[1]}mAh`);
    matches('Processor', /\b(?:Intel\s+)?(?:Core\s+)?i[3579]-\d{4,5}[A-Z]{0,3}\b/gi, (m) => m[0]);
    matches('Processor', /\b(?:AMD\s+)?Ryzen\s+[3579]\s+\d{4}[A-Z]{0,3}\b/gi, (m) => m[0]);
  }
  if (input.category === 'mobiles') {
    // Compact RAM/storage is accepted only for plausible, ordered mobile capacities.
    for (const m of text.matchAll(
      /(?:^|[\s,;])([1-9]\d?)\s*(?:GB\s*)?\/\s*(\d{2,4})\s*(?:GB\b)?(?=$|[\s,;.])/gi,
    )) {
      const ram = Number(m[1]);
      const storage = Number(m[2]);
      if (
        [2, 3, 4, 6, 8, 12, 16, 18, 24, 32].includes(ram) &&
        [16, 32, 64, 128, 256, 512, 1024].includes(storage) &&
        storage > ram
      ) {
        add('RAM', `${ram}GB`);
        add('Storage', `${storage}GB`);
      }
    }
    // A bare capacity is storage only for a phone and only at plausible storage sizes.
    matches(
      'Storage',
      /\b(32|64|128|256|512|1024)\s*GB\b(?!\s*(?:RAM|memory card|SD card|card|cloud)\b)/gi,
      (m) => `${m[1]}GB`,
    );
    matches(
      'Battery health',
      /\b(?:battery(?:\s+health)?|BH)\s*[:=]?\s*(100|[1-9]?\d)\s*%/gi,
      (m) => `${m[1]}%`,
    );
    matches(
      'Battery health',
      /\b(100|[1-9]?\d)\s*%\s*battery(?:\s+health)?\b/gi,
      (m) => `${m[1]}%`,
    );
    matches(
      'Battery health',
      /بیٹری(?:\s+ہیلتھ)?\s*[:=]?\s*(100|[1-9]?\d)\s*%/g,
      (m) => `${m[1]}%`,
    );
    const nonPta =
      /\b(?:non[ -]?PTA|not\s+PTA\s+approved|PTA\s*(?:is\s+)?(?:not\s+approved|unapproved|(?:approved\s+)?(?:nahi|nai|nahin)))\b|پی ٹی اے\s*نہیں/i.test(
        text,
      );
    if (nonPta) add('PTA status', 'Non-PTA');
    matches('PTA status', /\bPTA\s*approved\b/gi, () => 'Approved');
    for (const [key, token] of [
      ['Face ID', 'face\\s*id'],
      ['True Tone', 'true\\s*tone'],
    ] as const) {
      const negative = new RegExp(
        `\\b${token}\\s*(?:is\\s+)?(?:working\\s+(?:nahi|nai|nahin)|not\\s+working|does(?:n't| not)\\s+work|nahi\\s*(?:chalta|working)?|nai\\s*(?:chalta|working)?|faulty|broken)\\b`,
        'i',
      );
      const positive = new RegExp(
        `\\b${token}\\s*(?:is\\s+)?(?:working|works|okay|ok|chalta\\s+hai)\\b`,
        'i',
      );
      if (negative.test(text)) add(key, 'Not working');
      if (positive.test(text) && !negative.test(text)) add(key, 'Working');
    }
    matches(
      'Screen',
      /\b(?:screen|display)\s*(?:is\s+|was\s+)?(?:replaced|changed)\b/gi,
      () => 'Replaced',
    );
  }

  // Accessories: absence is explicit, never implied by a missing mention.
  if (devices) {
    for (const [key, token] of [
      ['Box', '(?:box|باکس)'],
      ['Charger', '(?:charger|چارجر)'],
    ] as const) {
      const neg = new RegExp(
        `(?:\\b(?:no|without|missing)\\s+${token}\\b(?!\\s+(?:issue|problem|fault))|${token}\\s*(?::\\s*)?(?:is\\s+)?(?:(?:included|available)\\s+(?:nahi|nai|nahin|نہیں)|not\\s+(?:included|available)|missing|nahi|nai|nahin|نہیں))`,
        'i',
      );
      const pos = new RegExp(
        `${token}\\s*(?::\\s*)?(?:is\\s+)?(?:included|available|only|hai|ha|ہے)(?=$|[\\s,;.])|\\bwith\\s+${token}\\b`,
        'i',
      );
      if (neg.test(text)) add(key, 'Not included');
      if (pos.test(text) && !neg.test(text)) add(key, 'Included');
    }
  }

  const clauses = text
    .split(/[,،;\n|•]|(?<!\d)\.(?!\d)/)
    .map(clean)
    .filter(Boolean);
  // Only unmistakable defects; "no scratches" must never become a scratch claim.
  const faults = clauses.filter(
    (c) =>
      /scratch|crack|dent|broken|faulty|leak|not working|replaced|screen changed|خراب|ٹوٹ|خراش/i.test(
        c,
      ) &&
      !/\b(?:no|without|not|never)\s+(?:any\s+)?(?:scratch\w*|crack\w*|dent\w*|fault\w*|leak\w*|replac\w*)\b|خراش نہیں/i.test(
        c,
      ),
  );
  if (faults.length && !candidates.has(specKey('Condition details'))) {
    const value = faults.join('; ');
    add(
      'Condition details',
      value.length <= 80 ? value : 'Disclosed faults / repairs — see description',
    );
  }
  for (const clause of clauses) {
    const colour = clause.match(
      /^(?:(?:colour|color)\s*[:=]?\s*)?(black|white|blue|red|green|grey|gray|silver|gold|pink|purple|yellow|orange|brown|beige)(?:\s+(?:colour|color))?$/i,
    );
    if (colour?.[1]) add('Colour', colour[1][0]?.toUpperCase() + colour[1].slice(1).toLowerCase());
  }

  if (input.category === 'vehicles') {
    matches(
      'Year',
      /\b(?:year|model(?:\s+year)?)\s*[:=]?\s*((?:19|20)\d{2})\b/gi,
      (m) => m[1] ?? '',
    );
    matches(
      'Mileage',
      /\b(\d{1,3}(?:,\d{3})+|\d{1,7})\s*(km|kms|kilometres|kilometers|miles)\b/gi,
      (m) => `${m[1]} ${/^mile/i.test(m[2] ?? '') ? 'miles' : 'km'}`,
    );
    matches('Engine capacity', /\b(\d{2,5})\s*cc\b/gi, (m) => `${m[1]}cc`);
    matches(
      'Transmission',
      /\b(automatic|manual|CVT)\s*(?:transmission|gearbox)?\b/gi,
      (m) => m[1] ?? '',
    );
    matches('Fuel type', /\b(petrol|diesel|hybrid|electric|CNG)\b/gi, (m) => m[1] ?? '');
  }
  if (input.category.startsWith('property-')) {
    matches(
      'Area',
      /\b(\d+(?:\.\d+)?)\s*(marla|kanal|sq\.?\s*ft|square\s*feet|sq\.?\s*yards?)\b/gi,
      (m) => `${m[1]} ${m[2]}`,
    );
    matches('Bedrooms', /\b(\d{1,2})\s*(?:bedrooms?|beds?)\b/gi, (m) => m[1] ?? '');
    matches('Bathrooms', /\b(\d{1,2})\s*(?:bathrooms?|baths?)\b/gi, (m) => m[1] ?? '');
    if (/\bunfurnished\b/i.test(text)) add('Furnished', 'No');
    if (/\bfully furnished\b/i.test(text)) add('Furnished', 'Yes');
  }
  if (input.category === 'home-appliances') {
    matches(
      'Capacity',
      /\b(\d{1,4}(?:\.\d+)?)\s*(kg|litres?|liters?|L|tons?)\b/gi,
      (m) => `${m[1]} ${m[2]}`,
    );
    matches('Power', /\b(\d{1,5}(?:\.\d+)?)\s*(watts?|kW)\b/gi, (m) => `${m[1]} ${m[2]}`);
    matches('Spin speed', /\b(\d{3,4})\s*rpm\b/gi, (m) => `${m[1]} rpm`);
    matches('Type', /\b(front|top)[ -]?load(?:ing)?\b/gi, (m) => `${m[1]} load`);
  }
  if (input.category === 'furniture') {
    matches('Seating capacity', /\b(\d{1,2})[ -]seater\b/gi, (m) => m[1] ?? '');
  }
  if (input.category === 'animals') {
    matches('Age', /\b(\d{1,2})\s*(months?|years?|weeks?)\s*old\b/gi, (m) => `${m[1]} ${m[2]}`);
  }

  // Conservative model recognition from the title; do not interpret comparison prose.
  if (
    input.category === 'mobiles' &&
    !/\b(?:case|cover|protector|charger|wanted|for parts from)\b/i.test(title)
  ) {
    const model = title.match(
      /\b(?:Samsung\s+)?(?:Galaxy\s+)?S\d{2}(?:\s*(?:Ultra|Plus|FE)|\+)?\b|\biPhone\s*\d{1,2}(?:e|\s*(?:Pro\s*Max|Pro|Plus|Mini))?\b|\b(?:Oppo|Vivo|Realme)\s+[A-Z]?\d{1,3}(?:\s*(?:Pro|Plus))?\b/gi,
    );
    if (model?.length === 1) {
      const value = model[0] ?? '';
      // A trailing '+' is not a word, so capture it explicitly after the match.
      const start = title.indexOf(value);
      add(
        'Model',
        value + (title[start + value.length] === '+' && !value.endsWith('+') ? '+' : ''),
      );
      if (/iphone/i.test(value)) add('Brand', 'Apple');
      else if (/^(?:Samsung\s+)?(?:Galaxy\s+)?S\d/i.test(value)) add('Brand', 'Samsung');
      else add('Brand', value.split(/\s+/)[0] ?? '');
    }
  }

  const specs: ProductSpec[] = [];
  const ambiguous: string[] = [];
  for (const values of candidates.values()) {
    if (values.length === 1 && values[0]) specs.push(values[0]);
    else if (values[0]) ambiguous.push(values[0].key);
  }
  return { specs, ambiguous };
}
