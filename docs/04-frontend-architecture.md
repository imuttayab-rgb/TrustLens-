# 04 — Frontend Architecture

Next.js 15 (App Router) · React 19 · TypeScript (strict) · Tailwind CSS 4 · TanStack Query · React Hook Form + Zod

## 1. Organising principle: feature-sliced, not type-sliced

The default `components/ · hooks/ · utils/` layout groups files by *what they are*. At ~50 components that
becomes a directory where nothing related is adjacent and deleting a feature means hunting through six
folders. TrustLens groups by **feature** — everything a feature needs lives in one folder — and reserves
type-based folders for genuinely global things.

```
src/features/trust-score/       ← all of it: components, hooks, api, types, validation
src/components/ui/              ← global, feature-agnostic primitives only
```

Rule: a feature may import from `packages/*`, `src/components/ui`, `src/lib`, and another feature's
**public `index.ts`** — never another feature's internals. Enforced by ESLint `no-restricted-imports`.

## 2. Directory structure

```
apps/web/
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── .env.example
├── public/
│   ├── icons/  images/  fonts/  og/
└── src/
    ├── app/                                  # App Router — routing ONLY, no business logic
    │   ├── layout.tsx                        # root: fonts, providers, <html lang>
    │   ├── error.tsx  not-found.tsx  global-error.tsx
    │   ├── (marketing)/                      # public, statically rendered
    │   │   ├── page.tsx                      # landing: what TrustLens is
    │   │   ├── how-it-works/page.tsx
    │   │   ├── for-marketplaces/page.tsx     # API pitch + docs link
    │   │   └── legal/{privacy,terms}/page.tsx
    │   ├── (public)/                         # buyer-facing lookup, server-rendered + cached
    │   │   ├── layout.tsx
    │   │   ├── check/page.tsx                # search a seller
    │   │   └── seller/[handle]/
    │   │       ├── page.tsx                  # public Trust Score page (RSC, ISR)
    │   │       ├── loading.tsx
    │   │       └── opengraph-image.tsx       # shareable score card
    │   ├── (auth)/
    │   │   ├── layout.tsx
    │   │   ├── login/  register/  forgot-password/  reset-password/
    │   │   └── verify-email/[token]/page.tsx
    │   ├── (seller)/                         # authenticated seller portal
    │   │   ├── layout.tsx                    # auth guard + seller shell
    │   │   └── dashboard/
    │   │       ├── page.tsx                  # score + what to improve
    │   │       ├── verification/
    │   │       │   ├── page.tsx              # checklist of the 4 checks
    │   │       │   ├── identity/page.tsx     # CNIC + selfie wizard
    │   │       │   ├── phone/page.tsx        # OTP
    │   │       │   └── email/page.tsx
    │   │       ├── listings/{page.tsx,new,[id]}
    │   │       ├── trust-score/page.tsx      # full breakdown + history
    │   │       ├── appeals/{page.tsx,new,[id]}
    │   │       └── settings/{profile,security,devices,notifications}
    │   ├── (admin)/                          # ADMIN + REVIEWER
    │   │   ├── layout.tsx                    # role guard + admin shell
    │   │   └── admin/
    │   │       ├── page.tsx                  # ops overview
    │   │       ├── reviews/{page.tsx,[id]}   # identity review queue
    │   │       ├── sellers/{page.tsx,[id]}
    │   │       ├── appeals/{page.tsx,[id]}
    │   │       ├── scoring/{page.tsx,models/[id]}   # weight tuning + simulation
    │   │       ├── api-clients/{page.tsx,[id]}
    │   │       └── audit-logs/page.tsx
    │   ├── api/                              # BFF only — never business logic
    │   │   ├── auth/session/route.ts         # sets/clears httpOnly cookies
    │   │   ├── auth/refresh/route.ts
    │   │   └── health/route.ts
    │   └── sitemap.ts  robots.ts
    │
    ├── features/                             # ★ the real code lives here
    │   ├── auth/
    │   │   ├── components/  LoginForm.tsx  RegisterForm.tsx  PasswordStrengthMeter.tsx
    │   │   ├── hooks/       useLogin.ts  useSession.ts  useLogout.ts
    │   │   ├── api/         auth.api.ts            # thin wrappers over the generated client
    │   │   ├── validation/  auth.schema.ts         # re-exports @trustlens/validation
    │   │   ├── types.ts     constants.ts
    │   │   └── index.ts                            # PUBLIC surface of the feature
    │   ├── verification-identity/
    │   │   ├── components/ CnicUploader.tsx  SelfieCapture.tsx  DocumentPreview.tsx
    │   │   │               VerificationWizard.tsx  OcrResultReview.tsx  ConsentGate.tsx
    │   │   ├── hooks/      useUploadIntent.ts  useIdentitySubmission.ts  useJobStatus.ts
    │   │   └── ...
    │   ├── verification-contact/    # phone OTP + email
    │   ├── verification-device/     # fingerprint collection + device list
    │   ├── listings/
    │   ├── trust-score/
    │   │   ├── components/ ScoreGauge.tsx  RiskBadge.tsx  SignalBreakdown.tsx
    │   │   │               ReasonList.tsx  ScoreHistoryChart.tsx  ImprovementTips.tsx
    │   │   └── ...
    │   ├── appeals/
    │   ├── admin-review/
    │   ├── admin-scoring/
    │   ├── admin-api-clients/
    │   └── notifications/
    │
    ├── components/
    │   ├── ui/                # re-exports @trustlens/ui + app-only primitives
    │   ├── layout/            # Header, Footer, Sidebar, SellerShell, AdminShell, Breadcrumbs
    │   ├── feedback/          # ErrorBoundary, EmptyState, LoadingState, Toaster
    │   └── data/              # DataTable, Pagination, FilterBar, SortHeader (generic)
    │
    ├── lib/
    │   ├── api/
    │   │   ├── client.ts      # configured openapi-fetch instance
    │   │   ├── server.ts      # server-side fetcher (forwards cookies, no client bundle)
    │   │   ├── interceptors.ts# 401 → refresh-once-then-logout, problem+json → AppError
    │   │   └── query-keys.ts  # centralised TanStack Query key factory
    │   ├── auth/              # session helpers, requireRole(), route guards
    │   ├── device/            # fingerprint collection (canvas/UA/screen/timezone signals)
    │   ├── format/            # date, currency, score, phone formatters
    │   └── utils/             # cn(), invariant(), sleep()
    │
    ├── providers/             # QueryProvider, ThemeProvider, ToastProvider, SessionProvider
    ├── stores/                # Zustand: uiStore (sidebar/modals), wizardStore (multi-step form)
    ├── hooks/                 # global: useDebounce, useMediaQuery, useClipboard, usePolling
    ├── config/                # site.ts, nav.ts, routes.ts, feature-flags.ts
    ├── types/                 # app-level TS types (API types come from packages/api-client)
    ├── styles/                # globals.css, tailwind layers, design tokens
    └── middleware.ts          # edge auth guard for (seller)/(admin) route groups
```

## 3. Rendering strategy per surface

| Surface | Strategy | Why |
|---|---|---|
| Marketing pages | Static (SSG) | No data, best possible Lighthouse score |
| Public seller score page | **RSC + ISR (revalidate 300 s) + tag-based revalidation** | Must be shareable, crawlable, and fast; TTL matches the Redis score TTL |
| Auth pages | Client components | Purely interactive |
| Seller dashboard | RSC shell fetches initial data, client components hydrate mutations | Fast first paint, live updates via TanStack Query |
| Verification wizards | Client | Camera, file input, polling — all browser APIs |
| Admin tables | Client with server-side pagination | Heavy filtering/sorting is a server concern |

> **WHY ISR on the public page rather than pure client fetching:** the buyer-facing score page is the
> product's shop window. Server rendering makes it linkable in a WhatsApp/marketplace chat with a proper
> OG preview card (`opengraph-image.tsx` renders the score gauge) — which is exactly how a buyer would
> actually share "check this seller before you pay".

## 4. Data layer

**Single source of truth: the backend's OpenAPI document.**

```
apps/api  ──(openapi.json)──►  tools/codegen  ──►  packages/api-client
                                                    ├── types.gen.ts     (openapi-typescript)
                                                    ├── client.ts        (openapi-fetch, typed)
                                                    └── index.ts
```

`pnpm codegen` regenerates; CI fails if the committed output differs from a fresh generation. A backend
field rename therefore breaks the **frontend type-check**, not production.

Layering above the generated client:

| Layer | Responsibility | Example |
|---|---|---|
| `packages/api-client` | Typed transport, generated | `client.GET("/api/v1/sellers/{id}")` |
| `lib/api/interceptors.ts` | Auth refresh, error normalisation, request-id capture | 401 → refresh once → retry once → logout |
| `features/*/api/*.api.ts` | Feature-specific request functions | `getTrustScore(sellerId)` |
| `features/*/hooks/use*.ts` | TanStack Query hooks, cache keys, invalidation | `useTrustScore(sellerId)` |
| Component | Rendering only | `<SignalBreakdown signals={data.signals} />` |

Query key factory (one place, prevents invalidation bugs):

```ts
export const qk = {
  trustScore: {
    current: (sellerId: string) => ['trust-score', sellerId, 'current'] as const,
    history: (sellerId: string) => ['trust-score', sellerId, 'history'] as const,
  },
  verification: { identity: (id: string) => ['verification', 'identity', id] as const },
  job:         { status: (jobId: string) => ['job', jobId] as const },
} as const;
```

### Long-running jobs in the UI

Identity verification takes ~15–30 s. `useJobStatus(jobId)` polls `GET /api/v1/jobs/{id}` with
`refetchInterval` that backs off (2 s → 5 s → 10 s), stops on a terminal status, and on success
invalidates `qk.trustScore.current(...)`. The wizard shows per-stage progress
(*uploading → reading CNIC → matching face → scoring*), which converts dead waiting time into visible
progress — the difference between "it's broken" and "it's working" in a demo.

## 5. State management

Four kinds of state, four tools — mixing them is the usual source of frontend mess.

| Kind | Tool | Examples |
|---|---|---|
| Server state | **TanStack Query** | Scores, listings, appeals, admin tables |
| URL state | **`nuqs` / searchParams** | Table filters, page, sort, tab — shareable and back-button correct |
| Form state | **React Hook Form** | Every form |
| Ephemeral client state | **Zustand** (small, sliced) | Sidebar open, active modal, wizard step |

There is deliberately **no Redux and no global app store**. Nearly all TrustLens state is server state;
a client store holding a copy of it would immediately drift.

Session state: the access token lives **in memory only** (never `localStorage`); the refresh token is an
httpOnly cookie the JS never touches. `SessionProvider` exposes `{user, roles, permissions, status}` and
Next `middleware.ts` guards route groups at the edge before any JS ships.

## 6. Forms and validation

Zod schemas live once in `packages/validation` and are consumed by both the app and (as a documentation
contract) mirrored by backend Pydantic models.

```
packages/validation/src/
├── auth.schema.ts        # registerSchema, loginSchema, passwordSchema
├── seller.schema.ts
├── identity.schema.ts    # cnicNumberSchema (13 digits + format), fileSchema (size/mime)
├── contact.schema.ts     # phoneE164Schema, otpSchema (6 digits)
├── listing.schema.ts
├── appeal.schema.ts
├── admin.schema.ts       # scoringWeightsSchema (weights must sum to 100)
└── common.schema.ts      # paginationSchema, uuidSchema, dateRangeSchema
```

Rules:
- Client validation is **UX, not security**. The backend re-validates everything; the client just fails fast.
- Multi-step wizards validate **per step** (`trigger(['field'])`) so a user is never told at step 4 that
  step 1 was wrong.
- File inputs validate size/type client-side for instant feedback and are re-validated server-side by
  magic bytes.
- One reusable `<FormField>` wrapper standardises label/description/error/aria wiring, so accessibility
  is correct by default rather than per-form.

## 7. Design system

`packages/ui` — headless-first, built on Radix primitives + `class-variance-authority` + Tailwind, shipped
as source (not compiled) so Tailwind can tree-shake and the app can override.

```
packages/ui/src/
├── primitives/   Button Input Select Checkbox Radio Switch Textarea Label
│                 Dialog Sheet Popover Tooltip Tabs Accordion Toast Badge Card
│                 Table Skeleton Avatar Progress Alert Separator DropdownMenu
├── composites/   FormField  FileDropzone  OtpInput  StepIndicator  ConfirmDialog
│                 DataTable  StatCard  CopyButton  EmptyState
├── charts/       ScoreGauge  SignalBar  TrendLine     # Recharts-based
├── icons/
├── styles/       tokens.css   # colour/space/radius/typography CSS variables
└── lib/          cn.ts  variants.ts
```

**Trust-score visual language** (a product decision, defined once so it can never drift):

| Risk level | Score | Token | Rule |
|---|---|---|---|
| Low risk | 70–100 | `--tl-risk-low` (green) | Always paired with the word "Low risk" |
| Medium risk | 40–69 | `--tl-risk-medium` (amber) | — |
| High risk | 0–39 | `--tl-risk-high` (red) | — |
| Unverified / insufficient data | — | `--tl-risk-unknown` (slate) | Never rendered as green |

Colour is **never the only carrier of meaning** — every badge carries text and an icon (WCAG 1.4.1), and
all pairings meet 4.5:1 contrast. That matters here beyond compliance: a colour-blind buyer misreading
amber as green is a person about to be defrauded.

## 8. Accessibility, i18n, performance

- **A11y:** semantic landmarks, keyboard-operable wizards, focus trapping in dialogs, `aria-live` on job
  progress and toasts, visible focus rings, `prefers-reduced-motion` respected for the gauge animation.
- **i18n (A12):** all copy through `packages/i18n` message catalogues from day one, English only shipped.
  Retrofitting i18n is far more expensive than routing strings through a catalogue now.
- **Performance budgets:** LCP < 2.0 s and initial JS < 180 KB gzip on the public score page; heavy
  dependencies (camera capture, chart library, fingerprint collector) are `next/dynamic` with
  `ssr: false`; images via `next/image`; fonts via `next/font` (self-hosted, no layout shift).

## 9. Error handling

| Level | Mechanism |
|---|---|
| Route | `error.tsx` per route group with a retry action |
| App | `global-error.tsx` |
| Component | `<ErrorBoundary>` around independently-failing widgets (charts, breakdown) |
| Request | `interceptors.ts` maps `application/problem+json` → `AppError {code, title, detail, requestId, fieldErrors}` |
| Form | Field errors mapped from the problem's `errors[]` array onto RHF fields by name |
| Toast | Non-blocking failures only |

Every user-visible error surfaces the `requestId` in small text. When a seller emails "verification
failed", that string turns a 30-minute log hunt into a single query.
