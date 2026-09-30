'use client';

import { cn } from '@trustlens/utils';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  { href: '/login', label: 'Login' },
  { href: '/register', label: 'Create account' },
] as const;

export function AuthTabs() {
  const pathname = usePathname();

  return (
    <div className="flex gap-6 border-b border-border">
      {TABS.map((tab) => {
        const active = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'relative inline-block pb-3 text-sm font-semibold transition-all duration-200',
              active
                ? 'text-brand'
                : 'text-muted-foreground hover:scale-[1.03] hover:text-foreground',
            )}
          >
            {tab.label}
            {active && (
              <span className="absolute inset-x-0 -bottom-px h-0.5 animate-fade-in rounded-full bg-brand" />
            )}
          </Link>
        );
      })}
    </div>
  );
}
