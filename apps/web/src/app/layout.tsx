import '@/styles/globals.css';

import { Providers } from '@/providers';
import { THEME_COOKIE, resolveTheme } from '@trustlens/ui';
import type { Metadata } from 'next';
import { cookies } from 'next/headers';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' });

export const metadata: Metadata = {
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
  const theme = resolveTheme((await cookies()).get(THEME_COOKIE)?.value);
  return (
    <html
      lang="en"
      className={`${inter.variable} ${theme === 'dark' ? 'dark' : ''}`}
      suppressHydrationWarning
    >
      <body className="min-h-dvh">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
