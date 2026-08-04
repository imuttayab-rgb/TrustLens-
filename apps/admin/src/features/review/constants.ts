/**
 * Mirrors MIN_DECISION_NOTE_CHARS in the admin use cases.
 *
 * Duplicated rather than imported: the domain is Python, and the API already
 * enforces it — this exists so the button disables before a round trip, not
 * as the rule itself.
 */
export const MIN_DECISION_NOTE_CHARS = 10;
