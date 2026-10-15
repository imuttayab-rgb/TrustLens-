/** Config module; defines LOCALES, Locale, DEFAULT_LOCALE, LOCALE_COOKIE, LOCALE_LABELS, RTL_LOCALES. */
export const LOCALES = ['en', 'ur'] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = 'en';
export const LOCALE_COOKIE = 'tl_locale';

export const LOCALE_LABELS: Record<Locale, string> = {
  en: 'English',
  ur: 'اردو',
};

export const RTL_LOCALES: readonly Locale[] = ['ur'];

export function isLocale(value: string | undefined): value is Locale {
  return (LOCALES as readonly string[]).includes(value ?? '');
}

export function dirForLocale(locale: Locale): 'rtl' | 'ltr' {
  return RTL_LOCALES.includes(locale) ? 'rtl' : 'ltr';
}
