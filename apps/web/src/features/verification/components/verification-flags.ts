/**
 * Compile-time identity-capture flags (NEXT_PUBLIC_* values are inlined at
 * build time, so changing one needs a web image rebuild).
 *
 * Kept in one module so the page header and the capture components always
 * agree on which flow is shown.
 */

/** Fourth image: the seller holding the physical ID beside their face. */
export const HOLD_ID_ENABLED = process.env.NEXT_PUBLIC_HOLD_ID_SCAN === 'true';

// Compile-time opt-in: changing this flag rebuilds the web image, and the
// current selfie flow stays untouched for all existing installations.
export const LIVE_FACE_SCAN_ENABLED = process.env.NEXT_PUBLIC_LIVE_FACE_SCAN === 'true' || HOLD_ID_ENABLED;

// Independent, default-off rollout: a Docker rebuild is required to switch
// ID capture to the webcam; existing stacks retain the old file picker.
export const LIVE_ID_SCAN_ENABLED = process.env.NEXT_PUBLIC_LIVE_ID_SCAN === 'true' || HOLD_ID_ENABLED;

/**
 * Step-by-step wizard: used when BOTH the card and the face are captured
 * live. With either flag off, the original single-page form is shown.
 */
export const LIVE_WIZARD_ENABLED = LIVE_ID_SCAN_ENABLED && LIVE_FACE_SCAN_ENABLED;
