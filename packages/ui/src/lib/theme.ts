/**
 * Theme constants, deliberately in their own module with no `'use client'`.
 *
 * A server component that imports a plain value from a client module does not
 * get the value — it gets a client reference proxy, and the comparison it
 * feeds silently evaluates false. That is exactly how the root layout ended up
 * omitting the `dark` class with no error anywhere: the cookie was read with
 * an undefined name, so it never matched.
 *
 * Keeping these here means both sides import the same real string.
 */
export const THEME_COOKIE = 'tl-theme';

export type Theme = 'light' | 'dark';

export const DEFAULT_THEME: Theme = 'dark';

/** Narrow an arbitrary cookie value to a theme. */
export function resolveTheme(value: string | undefined): Theme {
  return value === 'light' || value === 'dark' ? value : DEFAULT_THEME;
}
