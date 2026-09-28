'use client';

import { LogoutButton } from '@/features/auth';
import { NotificationBell } from '@/features/notifications';
import { LocaleSwitcher } from '@/i18n/LocaleSwitcher';
import { Button, ThemeToggle } from '@trustlens/ui';
import { Menu, X } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

export interface DashboardNavItem {
  href: string;
  label: string;
}

/**
 * Seven nav links plus notifications, language, theme and logout never fit
 * in one row below roughly 1000px - they used to just overflow the header
 * with no wrap and no scroll affordance, so anything past the visible edge
 * was there in the DOM but physically unreachable. That's what "the pages
 * aren't clickable" meant: not broken routes, an invisible-but-real link.
 *
 * `lg:` shows the full row like before; anything narrower collapses to a
 * button that opens every link in one column, the same pattern SiteNav
 * already uses on the marketing site.
 */
export function DashboardNav({ items }: { items: DashboardNavItem[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="flex items-center gap-1">
      <nav className="hidden items-center gap-1 text-sm lg:flex">
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="rounded-md px-3 py-2 text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <NotificationBell />
      <LocaleSwitcher className="ml-1 hidden lg:flex" />
      <ThemeToggle className="ml-1 hidden lg:inline-flex" />
      <LogoutButton className="ml-1 hidden lg:inline-flex" />

      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={open ? 'Close menu' : 'Open menu'}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="ml-1 lg:hidden"
      >
        {open ? (
          <X className="h-5 w-5" aria-hidden="true" />
        ) : (
          <Menu className="h-5 w-5" aria-hidden="true" />
        )}
      </Button>

      {open && (
        <div className="absolute inset-x-0 top-full z-30 border-t border-border/60 bg-background/95 backdrop-blur-xl lg:hidden">
          <nav className="mx-auto flex max-w-4xl flex-col gap-1 px-4 py-3 sm:px-6">
            {items.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className="rounded-md px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {item.label}
              </Link>
            ))}
            <div className="mt-2 flex items-center gap-2 border-t border-border/60 pt-3">
              <LocaleSwitcher />
              <ThemeToggle />
              <LogoutButton className="ml-auto" />
            </div>
          </nav>
        </div>
      )}
    </div>
  );
}
