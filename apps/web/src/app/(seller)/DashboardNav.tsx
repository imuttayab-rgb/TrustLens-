'use client';

import { cn } from '@trustlens/ui';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export interface DashboardNavItem {
  href: string;
  label: string;
}

/** Account tools supplement the shared header on every dashboard screen. */
export function DashboardNav({ items }: { items: DashboardNavItem[] }) {
  const pathname = usePathname();
  return (
    <div className="relative z-30 mb-6 flex min-w-0 items-center gap-2 rounded-xl border border-border bg-card p-2">
      <nav
        aria-label="Account navigation"
        className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto pb-1 text-sm"
      >
        {items.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== '/dashboard' && pathname.startsWith(`${item.href}/`));
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'shrink-0 rounded-md px-3 py-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                active
                  ? 'bg-primary/10 font-medium text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
