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
  'IDENTITY', 'PHONE', 'EMAIL', 'DEVICE', 'NETWORK', 'BEHAVIOUR', 'LISTING',
] as const;
export type SignalCategory = (typeof SIGNAL_CATEGORIES)[number];

export const SIGNAL_STATUSES = [
  'PASS', 'PARTIAL', 'FAIL', 'UNAVAILABLE', 'NOT_APPLICABLE',
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
  IDENTITY: 30, PHONE: 15, EMAIL: 10, DEVICE: 10, NETWORK: 10, BEHAVIOUR: 10, LISTING: 15,
};

// ── Verification ─────────────────────────────────────────────────────

export const VERIFICATION_STATUSES = [
  'NOT_STARTED', 'PENDING', 'PROCESSING', 'VERIFIED', 'REJECTED', 'EXPIRED', 'FAILED',
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
