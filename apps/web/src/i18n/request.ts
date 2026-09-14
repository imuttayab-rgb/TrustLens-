import type { AbstractIntlMessages } from 'next-intl';
import { cookies } from 'next/headers';
import { getRequestConfig } from 'next-intl/server';
import { DEFAULT_LOCALE, LOCALE_COOKIE, isLocale, type Locale } from './config';

const MESSAGE_LOADERS: Record<Locale, () => Promise<{ default: AbstractIntlMessages }>> = {
  en: () => import('../../messages/en.json'),
  ur: () => import('../../messages/ur.json'),
};

/**
 * No `[locale]` URL segment (I18N-01) - every existing route stays exactly
 * where it is. The locale comes from a cookie instead, the shape next-intl's
 * own "without i18n routing" example recommends when the alternative is
 * restructuring every route in an app this size.
 */
export default getRequestConfig(async () => {
  const store = await cookies();
  const cookieValue = store.get(LOCALE_COOKIE)?.value;
  const locale = isLocale(cookieValue) ? cookieValue : DEFAULT_LOCALE;
  const messages = (await MESSAGE_LOADERS[locale]()).default;

  return { locale, messages };
});
