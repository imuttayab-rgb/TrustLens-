/**
 * Shared Tailwind preset.
 *
 * The risk palette is defined ONCE here so the web app, the admin app and any
 * future surface cannot disagree about what "medium risk" looks like. Colour
 * is never the sole carrier of meaning - every badge also carries text and an
 * icon (WCAG 1.4.1) - which matters here beyond compliance: a colour-blind
 * buyer misreading amber as green is a person about to be defrauded.
 */
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        risk: {
          low: 'hsl(var(--risk-low))',
          'low-bg': 'hsl(var(--risk-low-bg))',
          medium: 'hsl(var(--risk-medium))',
          'medium-bg': 'hsl(var(--risk-medium-bg))',
          high: 'hsl(var(--risk-high))',
          'high-bg': 'hsl(var(--risk-high-bg))',
          unknown: 'hsl(var(--risk-unknown))',
          'unknown-bg': 'hsl(var(--risk-unknown-bg))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: { sans: ['var(--font-sans)', 'system-ui', 'sans-serif'] },
      keyframes: {
        'score-fill': { from: { strokeDashoffset: '999' }, to: { strokeDashoffset: 'var(--dash)' } },
      },
      animation: { 'score-fill': 'score-fill 900ms ease-out forwards' },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
