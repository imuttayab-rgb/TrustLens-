/** Next.js route/layout composition for layout.tsx: layout. */
import '@/styles/globals.css';

import { Providers } from '@/providers';
import { THEME_COOKIE, resolveTheme } from '@trustlens/ui';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { cookies } from 'next/headers';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' });

// Nonces require request-time rendering of every HTML document.
export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: { default: 'TrustLens Admin', template: '%s · TrustLens Admin' },
  // The admin panel must never be indexed. It is a separate deployment
  // precisely so it can be locked down independently of the public site.
  robots: { index: false, follow: false, nocache: true },
};

/**
 * Shell only. The staff gate and the sidebar live in the (dashboard) group so
 * that /login sits outside them — guarding the login page would redirect it
 * to itself.
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
