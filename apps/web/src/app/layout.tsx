/** Next.js route/layout composition for layout.tsx: layout. */
import '@/styles/globals.css';

import { Providers } from '@/providers';
import { AssistantWidget } from '@/features/assistant';
import { dirForLocale } from '@/i18n/config';
import { THEME_COOKIE, resolveTheme } from '@trustlens/ui';
import type { Metadata } from 'next';
import { NextIntlClientProvider } from 'next-intl';
import { getLocale, getMessages, getTranslations } from 'next-intl/server';
import { cookies } from 'next/headers';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' });

// Nonces require request-time rendering of every HTML document.
export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  manifest: '/manifest.webmanifest',
  title: { default: 'TrustLens', template: '%s · TrustLens' },
  description:
    'Check whether an online marketplace seller is genuine before you pay. ' +
    'TrustLens combines identity, phone, email, device and listing checks into ' +
    'one explainable Trust Score.',
  robots: { index: true, follow: true },
};

/**
 * Reading the theme from a cookie on the server is what makes the switch
 * flash-free: the correct class is present in the very first response,
 * rather than being applied by script after the browser has already painted.
 */
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Light is this app's own default, not the shared package's - the admin
  // app keeps dark as its default via the same `resolveTheme`, since only
  // the public-facing marketplace redesign called for a light-first look.
  const cookieValue = (await cookies()).get(THEME_COOKIE)?.value;
  const theme = cookieValue ? resolveTheme(cookieValue) : 'light';
  const locale = await getLocale();
  const messages = await getMessages();
  const t = await getTranslations('Common');
  const dir = dirForLocale(locale as Parameters<typeof dirForLocale>[0]);

  return (
    <html
      lang={locale}
      dir={dir}
      className={`${inter.variable} ${theme === 'dark' ? 'dark' : ''}`}
      suppressHydrationWarning
    >
      <body className="min-h-dvh">
        {/* Visually hidden until focused - the first tab stop for a keyboard
            or screen-reader user, so they don't have to tab through the whole
            nav on every single page just to reach the content. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {t('skipToContent')}
        </a>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <Providers>
            {children}
            <AssistantWidget />
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
