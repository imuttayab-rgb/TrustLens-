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
        brand: {
          DEFAULT: 'hsl(var(--brand))',
          2: 'hsl(var(--brand-2))',
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
        'score-fill': {
          from: { strokeDashoffset: '999' },
          to: { strokeDashoffset: 'var(--dash)' },
        },
        // Entrance: content arrives from slightly below, never from the side -
        // horizontal drift fights the reading direction on a text-heavy hero.
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(14px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        // A signal resolving from unknown to verified.
        'pop-in': {
          '0%': { opacity: '0', transform: 'scale(0.7)' },
          '70%': { opacity: '1', transform: 'scale(1.08)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        // Ambient background light. Very slow and very low contrast: it should
        // register as atmosphere, not as something moving on the page.
        drift: {
          '0%, 100%': { transform: 'translate3d(0,0,0) scale(1)' },
          '50%': { transform: 'translate3d(3%, -4%, 0) scale(1.08)' },
        },
        // A few pixels of vertical bob for a foreground illustration - unlike
        // `drift`, this one IS meant to read as gently alive, so it moves far
        // less and far slower than anything interactive on the page.
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        // Runs once behind the score arc as it settles.
        sheen: {
          from: { transform: 'translateX(-120%)' },
          to: { transform: 'translateX(220%)' },
        },
      },
      animation: {
        'score-fill': 'score-fill 1100ms cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'fade-up': 'fade-up 620ms cubic-bezier(0.16, 1, 0.3, 1) both',
        'fade-in': 'fade-in 500ms ease-out both',
        'pop-in': 'pop-in 420ms cubic-bezier(0.16, 1, 0.3, 1) both',
        drift: 'drift 22s ease-in-out infinite',
        float: 'float 6s ease-in-out infinite',
        sheen: 'sheen 1400ms ease-out 700ms both',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
