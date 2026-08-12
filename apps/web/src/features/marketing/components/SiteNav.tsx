'use client';

import { Button, ThemeToggle, cn } from '@trustlens/ui';
import { ShieldCheck } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

/**
 * Absolute, not bare fragments.
 *
 * These sections live on the landing page, but this nav renders on every
 * marketing route. `#checks` from `/docs/api` scrolls to nothing and looks
 * like a dead link; `/#checks` navigates home and then scrolls.
 */
const LINKS = [
  { href: '/#how-it-works', label: 'How it works' },
  { href: '/#checks', label: 'What we check' },
  { href: '/#explainable', label: 'Why explainable' },
  { href: '/docs/api', label: 'API docs' },
] as const;

export function SiteNav() {
  const [lifted, setLifted] = useState(false);

  // The bar earns its border and blur only once content is behind it, so at
  // rest the hero meets the top of the page with nothing drawn across it.
  useEffect(() => {
    const onScroll = () => setLifted(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={cn(
        'sticky top-0 z-50 transition-[background-color,border-color,backdrop-filter] duration-300',
        lifted
          ? 'border-b border-border/70 bg-background/80 backdrop-blur-xl'
          : 'border-b border-transparent bg-transparent',
      )}
    >
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-5 py-3.5 sm:px-8">
        <Link
          href="/"
          className="group flex items-center gap-2.5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand to-brand-2 transition-transform duration-300 group-hover:scale-105">
            <ShieldCheck
              className="h-4 w-4 text-[hsl(var(--background))]"
              strokeWidth={2.5}
              aria-hidden="true"
            />
          </span>
          <span className="leading-none">
            <span className="block text-sm font-bold tracking-tight">TrustLens</span>
            <span className="block text-[10px] text-muted-foreground">Trust before you deal.</span>
          </span>
        </Link>

        <nav className="ml-auto hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="group relative rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {link.label}
              {/* Grows from the centre on hover or keyboard focus. `group-*`
                  rather than a bare `hover:` - the underline must react to the
                  link, not to the one-pixel strip it lives in. */}
              <span
                aria-hidden="true"
                className="absolute inset-x-3 -bottom-0.5 h-px origin-center scale-x-0 bg-brand transition-transform duration-300 group-hover:scale-x-100 group-focus-visible:scale-x-100"
              />
            </a>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2 md:ml-0">
          <ThemeToggle />
          <Button asChild variant="ghost" size="sm">
            <Link href="/login">Log in</Link>
          </Button>
          <Button
            asChild
            size="sm"
            className="bg-gradient-to-r from-brand to-brand-2 font-semibold text-[hsl(var(--background))] shadow-[0_6px_24px_-8px_hsl(var(--brand)/0.7)] transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]"
          >
            <Link href="/register">Get verified</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
