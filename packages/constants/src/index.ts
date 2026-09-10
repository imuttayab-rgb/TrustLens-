/**
 * Cross-app constants.
 *
 * These values appear in the backend, both frontends and the docs. Keeping
 * one TypeScript definition (mirroring `trustlens.core.domain.enums`) is what
 * stops them drifting into a bug nobody notices until a demo.
 */

// ── Risk bands (assumption A1) ───────────────────────────────────────

export const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'UNKNOWN'] as const;
export type RiskLevel = (typeof RISK_LEVELS)[number];

/** Inclusive upper bounds. 39 is HIGH, 40 is MEDIUM, 69 is MEDIUM, 70 is LOW. */
export const RISK_THRESHOLDS = { HIGH_MAX: 39, MEDIUM_MAX: 69 } as const;

export function bandFor(score: number): RiskLevel {
  if (score <= RISK_THRESHOLDS.HIGH_MAX) return 'HIGH';
  if (score <= RISK_THRESHOLDS.MEDIUM_MAX) return 'MEDIUM';
  return 'LOW';
}

/**
 * Presentation for each band.
 *
 * `UNKNOWN` is slate, never green or red: a brand-new honest seller and a
 * proven scammer must not render identically, and neither should be given a
 * colour that implies a verdict we have not reached.
 */
export const RISK_PRESENTATION: Record<
  RiskLevel,
  { label: string; token: string; description: string }
> = {
  LOW: {
    label: 'Low risk',
    token: 'risk-low',
    description: 'Multiple independent checks passed. Proceed with normal caution.',
  },
  MEDIUM: {
    label: 'Medium risk',
    token: 'risk-medium',
    description: 'Only partly verified. Ask for more proof before paying.',
  },
  HIGH: {
    label: 'High risk',
    token: 'risk-high',
    description: 'Weak or contradicted verification. High scam risk.',
  },
  UNKNOWN: {
    label: 'Not enough information',
    token: 'risk-unknown',
    description: 'Not enough checks have been completed to judge this seller.',
  },
};

// ── Signals ──────────────────────────────────────────────────────────

export const SIGNAL_CATEGORIES = [
  'IDENTITY',
  'PHONE',
  'EMAIL',
  'DEVICE',
  'NETWORK',
  'BEHAVIOUR',
  'LISTING',
] as const;
export type SignalCategory = (typeof SIGNAL_CATEGORIES)[number];

export const SIGNAL_STATUSES = [
  'PASS',
  'PARTIAL',
  'FAIL',
  'UNAVAILABLE',
  'NOT_APPLICABLE',
] as const;
export type SignalStatus = (typeof SIGNAL_STATUSES)[number];

export const CATEGORY_LABELS: Record<SignalCategory, string> = {
  IDENTITY: 'Identity',
  PHONE: 'Phone',
  EMAIL: 'Email',
  DEVICE: 'Device',
  NETWORK: 'Network',
  BEHAVIOUR: 'Account history',
  LISTING: 'Listings',
};

/** v1 weights. Mirrors the `scoring_weights` seed - shown in the checklist. */
export const CATEGORY_MAX_POINTS: Record<SignalCategory, number> = {
  IDENTITY: 30,
  PHONE: 15,
  EMAIL: 10,
  DEVICE: 10,
  NETWORK: 10,
  BEHAVIOUR: 10,
  LISTING: 15,
};

// ── Verification ─────────────────────────────────────────────────────

export const VERIFICATION_STATUSES = [
  'NOT_STARTED',
  'PENDING',
  'PROCESSING',
  'VERIFIED',
  'REJECTED',
  'EXPIRED',
  'FAILED',
] as const;
export type VerificationStatus = (typeof VERIFICATION_STATUSES)[number];

export const VERIFICATION_LABELS: Record<VerificationStatus, string> = {
  NOT_STARTED: 'Not started',
  PENDING: 'Awaiting confirmation',
  PROCESSING: 'Checking…',
  VERIFIED: 'Verified',
  REJECTED: 'Rejected',
  EXPIRED: 'Expired',
  FAILED: 'Could not be checked',
};

export const USER_ROLES = ['BUYER', 'SELLER', 'REVIEWER', 'ADMIN'] as const;
export type UserRole = (typeof USER_ROLES)[number];

// ── Uploads ──────────────────────────────────────────────────────────

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const;

// ── Routes ───────────────────────────────────────────────────────────

export const ROUTES = {
  home: '/',
  check: '/check',
  apiDocs: '/docs/api',
  seller: (handle: string) => `/seller/${handle}`,
  login: '/login',
  register: '/register',
  dashboard: '/dashboard',
  verification: '/dashboard/verification',
  identity: '/dashboard/verification/identity',
  phone: '/dashboard/verification/phone',
  listings: '/dashboard/listings',
  trustScore: '/dashboard/trust-score',
  appeals: '/dashboard/appeals',
  settings: '/dashboard/settings',
} as const;

export const ADMIN_ROUTES = {
  overview: '/',
  reviews: '/reviews',
  sellers: '/sellers',
  appeals: '/appeals',
  scoring: '/scoring',
  apiClients: '/api-clients',
  auditLogs: '/audit-logs',
} as const;

/** Polling backoff for long jobs: 2s, then 5s, then 10s. */
export const JOB_POLL_INTERVALS_MS = [2000, 5000, 10_000] as const;

// ── Listing categories ───────────────────────────────────────────────

/**
 * The only categories a listing may carry.
 *
 * A controlled vocabulary rather than free text, because the price signal
 * compares a listing against the median of its own category. With free text,
 * sellers produced "Mobile Phones", "mobile-phones" and "mobiles" as three
 * separate buckets for one category - so a phone was never compared against
 * other phones, and "too good to be true" could not fire.
 *
 * Stored as the slug. Never renamed in place: an existing listing's category
 * would silently change meaning. Add a new entry and migrate instead.
 */
export const LISTING_CATEGORIES = [
  'mobiles',
  'electronics',
  'computers',
  'vehicles',
  'vehicle-parts',
  'property-sale',
  'property-rent',
  'home-appliances',
  'furniture',
  'fashion',
  'books-hobbies',
  'animals',
  'services',
  'other',
] as const;

export type ListingCategory = (typeof LISTING_CATEGORIES)[number];

export const LISTING_CATEGORY_LABELS: Record<ListingCategory, string> = {
  mobiles: 'Mobile phones',
  electronics: 'Electronics',
  computers: 'Computers & tablets',
  vehicles: 'Vehicles',
  'vehicle-parts': 'Vehicle parts & accessories',
  'property-sale': 'Property for sale',
  'property-rent': 'Property for rent',
  'home-appliances': 'Home appliances',
  furniture: 'Furniture & home',
  fashion: 'Fashion & beauty',
  'books-hobbies': 'Books, sports & hobbies',
  animals: 'Animals',
  services: 'Services',
  other: 'Other',
};

// ── Location (city / area) ──────────────────────────────────────────

/**
 * City -> area, the same two-step picker OLX Pakistan uses instead of a
 * free-text city field: "Lahore" alone does not narrow a buyer's search
 * meaningfully in a city of 13 million people, and free text produced the
 * same "Lahore" / "lahore" / "LHR" fragmentation category slugs were built
 * to avoid (see LISTING_CATEGORIES above).
 *
 * Coverage is the ten largest cities with their well-known
 * neighbourhoods/towns, not exhaustive - "Other" is always offered as an
 * escape hatch so a real location is never blocked by a missing entry.
 */
export const PAKISTAN_LOCATIONS = {
  Lahore: [
    'Gulberg',
    'DHA',
    'Johar Town',
    'Model Town',
    'Bahria Town',
    'Askari',
    'Cantt',
    'Iqbal Town',
    'Township',
    'Wapda Town',
    'Garden Town',
    'Faisal Town',
    'Allama Iqbal Town',
    'Shalimar',
    'Other',
  ],
  Karachi: [
    'Clifton',
    'DHA',
    'Gulshan-e-Iqbal',
    'North Nazimabad',
    'Malir',
    'Korangi',
    'Saddar',
    'Gulistan-e-Johar',
    'PECHS',
    'Nazimabad',
    'Federal B Area',
    'Bahadurabad',
    'Other',
  ],
  Islamabad: [
    'F-6',
    'F-7',
    'F-8',
    'F-10',
    'F-11',
    'G-9',
    'G-10',
    'G-11',
    'E-11',
    'Bahria Town',
    'DHA',
    'Blue Area',
    'Other',
  ],
  Rawalpindi: [
    'Saddar',
    'Bahria Town',
    'DHA',
    'Satellite Town',
    'Chaklala',
    'Westridge',
    'Gulraiz',
    'Other',
  ],
  Faisalabad: ['Madina Town', 'Peoples Colony', 'D Ground', 'Gulberg', 'Samanabad', 'Other'],
  Multan: ['Cantt', 'Gulgasht Colony', 'Shah Rukn-e-Alam', 'Bosan Road', 'Other'],
  Peshawar: ['Hayatabad', 'University Town', 'Cantt', 'Gulbahar', 'Other'],
  Quetta: ['Cantt', 'Satellite Town', 'Jinnah Town', 'Other'],
  Gujranwala: ['Model Town', 'Satellite Town', 'Civil Lines', 'Other'],
  Sialkot: ['Cantt', 'Model Town', 'Paris Road', 'Other'],
  Other: ['Other'],
} as const;

export const PAKISTAN_CITIES = Object.keys(
  PAKISTAN_LOCATIONS,
) as (keyof typeof PAKISTAN_LOCATIONS)[];

export type PakistanCity = (typeof PAKISTAN_CITIES)[number];

export function areasForCity(city: string | null | undefined): readonly string[] {
  if (city && city in PAKISTAN_LOCATIONS) {
    return PAKISTAN_LOCATIONS[city as PakistanCity];
  }
  return PAKISTAN_LOCATIONS.Other;
}
