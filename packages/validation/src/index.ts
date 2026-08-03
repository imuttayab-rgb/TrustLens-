/**
 * Zod schemas shared by forms and the BFF.
 *
 * These mirror the backend Pydantic models. Client validation is UX, not
 * security - the backend re-validates everything - but keeping the rules in
 * one place stops the two halves disagreeing about what a valid CNIC or phone
 * number looks like.
 */
import { z } from 'zod';
import { ALLOWED_IMAGE_TYPES, LISTING_CATEGORIES, MAX_UPLOAD_BYTES } from '@trustlens/constants';

// ── Primitives ───────────────────────────────────────────────────────

export const uuidSchema = z.string().uuid('Invalid identifier.');

export const emailSchema = z
  .string()
  .trim()
  .toLowerCase()
  .min(3, 'Enter an email address.')
  .max(254)
  .email('Enter a valid email address.');

/**
 * E.164. The backend normalises spaces and dashes too, but showing the
 * expected shape up front saves a round trip.
 */
export const phoneSchema = z
  .string()
  .trim()
  .transform((v) => v.replace(/[\s\-()]/g, ''))
  .pipe(z.string().regex(/^\+[1-9]\d{7,14}$/, 'Use international format, e.g. +923001234567.'));

/** Pakistani CNIC: 5 + 7 + 1 digits. */
export const cnicSchema = z
  .string()
  .trim()
  .regex(/^\d{5}-?\d{7}-?\d$/, 'Enter a 13-digit CNIC, e.g. 35202-1234567-1.');

export const otpSchema = z
  .string()
  .trim()
  .regex(/^\d{6}$/, 'Enter the 6-digit code.');

const COMMON_PASSWORDS = new Set([
  'password',
  'password123',
  '123456789012',
  'qwertyuiop',
  'letmein12345',
  'trustlens123',
]);

export const passwordSchema = z
  .string()
  .min(12, 'Use at least 12 characters.')
  .max(128, 'That password is too long.')
  .refine((v) => !COMMON_PASSWORDS.has(v.toLowerCase()), 'This password is too common.')
  .refine((v) => new Set(v).size >= 5, 'Use a wider variety of characters.');

// ── Auth ─────────────────────────────────────────────────────────────

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, 'Enter your password.'),
});
export type LoginInput = z.infer<typeof loginSchema>;

export const registerSchema = z
  .object({
    email: emailSchema,
    password: passwordSchema,
    confirmPassword: z.string(),
    fullName: z.string().trim().min(2, 'Enter your full name.').max(150),
    asSeller: z.boolean().default(false),
    acceptedTerms: z.literal(true, {
      errorMap: () => ({ message: 'You must accept the terms to continue.' }),
    }),
  })
  .refine((v) => v.password === v.confirmPassword, {
    message: 'Passwords do not match.',
    path: ['confirmPassword'],
  })
  .refine((v) => !v.password.toLowerCase().includes(v.email.split('@')[0] ?? ' '), {
    message: 'Do not use your email address in your password.',
    path: ['password'],
  });
export type RegisterInput = z.infer<typeof registerSchema>;

export const resetPasswordSchema = z
  .object({ token: z.string().min(16), password: passwordSchema, confirmPassword: z.string() })
  .refine((v) => v.password === v.confirmPassword, {
    message: 'Passwords do not match.',
    path: ['confirmPassword'],
  });

// ── Verification ─────────────────────────────────────────────────────

export const imageFileSchema = z
  .instanceof(File)
  .refine((f) => f.size > 0, 'That file is empty.')
  .refine(
    (f) => f.size <= MAX_UPLOAD_BYTES,
    `Images must be ${Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)} MB or smaller.`,
  )
  .refine(
    (f) => (ALLOWED_IMAGE_TYPES as readonly string[]).includes(f.type),
    'Upload a JPEG, PNG or WEBP image.',
  );

export const identitySubmissionSchema = z.object({
  cnicFront: imageFileSchema,
  cnicBack: imageFileSchema,
  selfie: imageFileSchema,
  biometricConsent: z.literal(true, {
    errorMap: () => ({
      message: 'We need your consent to compare your selfie with your ID photo.',
    }),
  }),
});

export const requestOtpSchema = z.object({ phoneNumber: phoneSchema });
export const verifyOtpSchema = z.object({ code: otpSchema });

// ── Seller & listings ────────────────────────────────────────────────

export const becomeSellerSchema = z.object({
  displayName: z.string().trim().min(2, 'Enter a display name.').max(150),
  businessType: z.string().max(50).optional(),
  city: z.string().max(80).optional(),
  countryCode: z.string().length(2, 'Use a 2-letter country code.').optional(),
});

export const listingSchema = z.object({
  title: z.string().trim().min(3, 'Enter a title.').max(250),
  description: z.string().trim().min(10, 'Describe the item in at least 10 characters.').max(8000),
  price: z.coerce.number().nonnegative('Price cannot be negative.').optional(),
  currency: z.string().length(3).optional(),
  // A fixed vocabulary, not free text. The price signal compares a listing
  // against the median of its own category, and free text produced
  // "Mobile Phones", "mobile-phones" and "mobiles" as three separate buckets -
  // so a phone was never compared against other phones.
  category: z.enum(LISTING_CATEGORIES).optional(),
  city: z.string().max(80).optional(),
});
export type ListingInput = z.infer<typeof listingSchema>;

// ── Appeals ──────────────────────────────────────────────────────────

export const appealSchema = z.object({
  trustScoreId: uuidSchema,
  reasonCategory: z.enum([
    'IDENTITY_INCORRECT',
    'PHONE_INCORRECT',
    'LISTING_MISJUDGED',
    'DEVICE_INCORRECT',
    'OTHER',
  ]),
  reason: z
    .string()
    .trim()
    .min(20, 'Explain in at least 20 characters so a reviewer can act on it.')
    .max(4000),
});

// ── Admin ────────────────────────────────────────────────────────────

/**
 * Enabled weights must sum to 100 - the same invariant the domain and a
 * database CHECK enforce. Catching it in the form means an admin never
 * submits a model that would be rejected downstream.
 */
export const scoringWeightsSchema = z
  .object({
    weights: z
      .array(
        z.object({
          signalCode: z.string(),
          weight: z.number().min(0).max(100),
          enabled: z.boolean(),
        }),
      )
      .min(1),
  })
  .refine(
    (v) =>
      Math.abs(v.weights.filter((w) => w.enabled).reduce((s, w) => s + w.weight, 0) - 100) < 0.001,
    { message: 'Enabled weights must add up to exactly 100.', path: ['weights'] },
  );

export const overrideScoreSchema = z.object({
  score: z.coerce.number().int().min(0).max(100),
  reason: z
    .string()
    .trim()
    .min(10, 'A written reason is required to override a computed score.')
    .max(1000),
});

export const paginationSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  perPage: z.coerce.number().int().min(1).max(100).default(20),
});
