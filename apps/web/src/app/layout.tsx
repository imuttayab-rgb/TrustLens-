import '@/styles/globals.css';

import { Providers } from '@/providers';
import type { Metadata } from 'next';
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-dvh">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
