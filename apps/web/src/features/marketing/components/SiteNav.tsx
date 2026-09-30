'use client';

import { LogoutButton } from '@/features/auth';
import { LocaleSwitcher } from '@/i18n/LocaleSwitcher';
import { useSession } from '@/lib/auth/use-session';
import { useNotifications } from '@/features/notifications';
import { LISTING_CATEGORY_LABELS } from '@trustlens/constants';
import { Button, ThemeToggle, cn } from '@trustlens/ui';
import { ChevronDown, Heart, Menu, MessageCircle, Plus, ShieldCheck, User, X } from 'lucide-react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { NAV_CATEGORIES } from '../nav-categories';

function CategoriesMenu({ label }: { label: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="group flex items-center gap-1 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {label}
        <ChevronDown
          className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-180')}
          aria-hidden="true"
        />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-56 rounded-lg border border-border bg-card p-1.5 shadow-lg">
          {NAV_CATEGORIES.map((category) => (
            <Link
              key={category}
              href={`/browse?category=${category}`}
              onClick={() => setOpen(false)}
              className="block rounded-md px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted"
            >
              {LISTING_CATEGORY_LABELS[category]}
            </Link>
          ))}
          <Link
            href="/browse"
            onClick={() => setOpen(false)}
            className="block rounded-md px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-muted"
          >
            All categories
          </Link>
        </div>
      )}
    </div>
  );
}

export function SiteNav() {
  const t = useTranslations('SiteNav');
  const tc = useTranslations('Common');
  const { data: session } = useSession();
  const { data: notifications } = useNotifications(Boolean(session));
  const unread = session ? (notifications?.unreadCount ?? 0) > 0 : false;
  const pathname = usePathname();
  const [lifted, setLifted] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setLifted(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const links = [
    { href: '/', key: 'marketplace' },
    { href: '/check', key: 'trustCheck' },
    { href: '/safety', key: 'safeMeet', badge: 'New' },
  ] as const;

  return (
    <header
      className={cn(
        'sticky top-0 z-50 border-b bg-background/80 backdrop-blur-xl transition-[background-color,border-color,backdrop-filter] duration-300',
        lifted ? 'border-border/70 bg-background/90 backdrop-blur-xl' : 'border-border/40',
      )}
    >
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-5 py-3.5 sm:px-8">
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
          <span className="text-base font-bold tracking-tight">TrustLens</span>
        </Link>

        <nav className="ml-4 hidden items-center gap-0.5 lg:flex">
          {links.slice(0, 1).map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'group relative rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  active ? 'text-primary' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {t(link.key)}
                <span
                  aria-hidden="true"
                  className={cn(
                    'absolute inset-x-3 -bottom-0.5 h-0.5 origin-center rounded-full bg-brand transition-transform duration-300',
                    active ? 'scale-x-100' : 'scale-x-0 group-hover:scale-x-100',
                  )}
                />
              </Link>
            );
          })}
          <CategoriesMenu label={t('categories')} />
          {links.slice(1).map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'group relative flex items-center gap-1.5 rounded-md px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  active ? 'text-primary' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {t(link.key)}
                {'badge' in link && link.badge && (
                  <span className="rounded-full bg-brand/15 px-1.5 py-0.5 text-[10px] font-semibold text-brand">
                    {link.badge}
                  </span>
                )}
                <span
                  aria-hidden="true"
                  className={cn(
                    'absolute inset-x-3 -bottom-0.5 h-0.5 origin-center rounded-full bg-brand transition-transform duration-300',
                    active ? 'scale-x-100' : 'scale-x-0 group-hover:scale-x-100',
                  )}
                />
              </Link>
            );
          })}
          <Link
            href="/dashboard/messages"
            className="group relative flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <MessageCircle
              className="h-3.5 w-3.5 transition-transform duration-200 group-hover:scale-110"
              aria-hidden="true"
            />
            {t('messages')}
            {unread && (
              <span
                className="absolute right-1 top-1.5 h-1.5 w-1.5 animate-pulse rounded-full bg-brand"
                aria-hidden="true"
              />
            )}
            <span
              aria-hidden="true"
              className="absolute inset-x-3 -bottom-0.5 h-0.5 origin-center scale-x-0 rounded-full bg-brand transition-transform duration-300 group-hover:scale-x-100"
            />
          </Link>
          <Link
            href="/favourites"
            className="group relative flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Heart
              className="h-3.5 w-3.5 transition-transform duration-200 group-hover:scale-110"
              aria-hidden="true"
            />
            {t('favourites')}
            <span
              aria-hidden="true"
              className="absolute inset-x-3 -bottom-0.5 h-0.5 origin-center scale-x-0 rounded-full bg-brand transition-transform duration-300 group-hover:scale-x-100"
            />
          </Link>
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <LocaleSwitcher className="hidden sm:flex" />
          <ThemeToggle />
          {session ? (
            <>
              <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
                <Link href="/dashboard">{tc('dashboard')}</Link>
              </Button>
              <LogoutButton className="hidden sm:inline-flex" />
            </>
          ) : (
            <Button asChild variant="ghost" size="sm" className="hidden gap-1.5 sm:inline-flex">
              <Link href="/login">
                <User className="h-3.5 w-3.5" aria-hidden="true" />
                {tc('logIn')}
              </Link>
            </Button>
          )}
          <Button
            asChild
            size="sm"
            className="hidden gap-1.5 bg-gradient-to-r from-brand to-brand-2 font-semibold text-[hsl(var(--background))] shadow-[0_6px_24px_-8px_hsl(var(--brand)/0.7)] transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98] sm:inline-flex"
          >
            <Link href="/dashboard/listings/new">
              <Plus className="h-4 w-4" aria-hidden="true" />
              {t('postAnAd')}
            </Link>
          </Button>
          <button
            type="button"
            aria-label={menuOpen ? tc('closeMenu') : tc('openMenu')}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
            className="grid h-9 w-9 place-items-center rounded-md text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
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
        <div className="border-t border-border/60 bg-background/95 backdrop-blur-xl lg:hidden">
          <nav className="mx-auto flex max-w-7xl flex-col gap-1 px-5 py-3 sm:px-8">
            <Link
              href="/"
              onClick={() => setMenuOpen(false)}
              className="rounded-md px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {t('marketplace')}
            </Link>
            {NAV_CATEGORIES.map((category) => (
              <Link
                key={category}
                href={`/browse?category=${category}`}
                onClick={() => setMenuOpen(false)}
                className="rounded-md px-3 py-2.5 pl-6 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {LISTING_CATEGORY_LABELS[category]}
              </Link>
            ))}
            <Link
              href="/check"
              onClick={() => setMenuOpen(false)}
              className="rounded-md px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {t('trustCheck')}
            </Link>
            <Link
              href="/safety"
              onClick={() => setMenuOpen(false)}
              className="rounded-md px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {t('safeMeet')}
            </Link>
            <Link
              href="/dashboard/messages"
              onClick={() => setMenuOpen(false)}
              className="rounded-md px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {t('messages')}
            </Link>
            <Link
              href="/favourites"
              onClick={() => setMenuOpen(false)}
              className="rounded-md px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {t('favourites')}
            </Link>
            <div className="mt-3 border-t border-border/60 pt-3">
              <LocaleSwitcher />
            </div>
            <div className="mt-2 flex items-center gap-2">
              {session ? (
                <>
                  <Button asChild variant="outline" size="sm" className="flex-1">
                    <Link href="/dashboard" onClick={() => setMenuOpen(false)}>
                      {tc('dashboard')}
                    </Link>
                  </Button>
                  <LogoutButton className="flex-1" />
                </>
              ) : (
                <Button asChild variant="ghost" size="sm" className="flex-1 gap-1.5">
                  <Link href="/login" onClick={() => setMenuOpen(false)}>
                    <User className="h-3.5 w-3.5" aria-hidden="true" />
                    {tc('logIn')}
                  </Link>
                </Button>
              )}
              <Button
                asChild
                size="sm"
                className="flex-1 gap-1.5 bg-gradient-to-r from-brand to-brand-2 font-semibold text-[hsl(var(--background))]"
              >
                <Link href="/dashboard/listings/new" onClick={() => setMenuOpen(false)}>
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  {t('postAnAd')}
                </Link>
              </Button>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
