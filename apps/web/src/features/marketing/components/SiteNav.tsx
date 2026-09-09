'use client';

import { Button, ThemeToggle, cn } from '@trustlens/ui';
import { Menu, ShieldCheck, X } from 'lucide-react';
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
  { href: '/browse', label: 'Browse' },
  { href: '/#how-it-works', label: 'How it works' },
  { href: '/#checks', label: 'What we check' },
  { href: '/#explainable', label: 'Why explainable' },
  { href: '/docs/api', label: 'API docs' },
] as const;

export function SiteNav() {
  const [lifted, setLifted] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // The bar is always visible (background + border) so it reads as a nav on
  // any hero, light or dark; scrolling just deepens the blur/border for
  // legibility over moving content underneath.
  useEffect(() => {
    const onScroll = () => setLifted(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={cn(
        'sticky top-0 z-50 border-b bg-background/80 backdrop-blur-xl transition-[background-color,border-color,backdrop-filter] duration-300',
        lifted ? 'border-border/70 bg-background/90 backdrop-blur-xl' : 'border-border/40',
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
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link href="/login">Log in</Link>
          </Button>
          <Button
            asChild
            size="sm"
            className="hidden bg-gradient-to-r from-brand to-brand-2 font-semibold text-[hsl(var(--background))] shadow-[0_6px_24px_-8px_hsl(var(--brand)/0.7)] transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98] sm:inline-flex"
          >
            <Link href="/register">Get verified</Link>
          </Button>
          <button
            type="button"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
            className="grid h-9 w-9 place-items-center rounded-md text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:hidden"
          >
            {menuOpen ? (
              <X className="h-5 w-5" aria-hidden="true" />
            ) : (
              <Menu className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      {menuOpen && (
        <div className="border-t border-border/60 bg-background/95 backdrop-blur-xl md:hidden">
          <nav className="mx-auto flex max-w-6xl flex-col gap-1 px-5 py-3 sm:px-8">
            {LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className="rounded-md px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
            <div className="mt-2 flex items-center gap-2 border-t border-border/60 pt-3">
              <Button asChild variant="ghost" size="sm" className="flex-1">
                <Link href="/login" onClick={() => setMenuOpen(false)}>
                  Log in
                </Link>
              </Button>
              <Button
                asChild
                size="sm"
                className="flex-1 bg-gradient-to-r from-brand to-brand-2 font-semibold text-[hsl(var(--background))]"
              >
                <Link href="/register" onClick={() => setMenuOpen(false)}>
                  Get verified
                </Link>
              </Button>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
