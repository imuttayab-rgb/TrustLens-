/**
 * A cheap, client-only heuristic for SOC-01's "risky-link/payment-pressure
 * warning" gap - not spam detection or content moderation (which would need
 * a real backend classifier), just a pattern match that flags the two
 * classic scam shapes a marketplace chat sees: a request to pay/send money
 * before meeting, and a link the buyer/seller is being pushed to open.
 * False positives are fine here - it's an inline hint, not a block.
 */

const PAYMENT_PRESSURE_PATTERN =
  /\b(advance payment|pay (now|first|before)|send (money|payment|cash)|wire transfer|western union|easypaisa|jazzcash|bank transfer|gift card|deposit first|booking fee)\b/i;

const URL_PATTERN = /https?:\/\/\S+|www\.\S+/i;

export interface MessageRiskFlags {
  paymentPressure: boolean;
  hasLink: boolean;
}

export function assessMessageRisk(body: string): MessageRiskFlags {
  return {
    paymentPressure: PAYMENT_PRESSURE_PATTERN.test(body),
    hasLink: URL_PATTERN.test(body),
  };
}

export function hasRiskFlags(flags: MessageRiskFlags): boolean {
  return flags.paymentPressure || flags.hasLink;
}
