import { RequireStaff } from '@/features/auth';
import { ADMIN_ROUTES } from '@trustlens/constants';
import { Ambient, ThemeToggle } from '@trustlens/ui';
import { ShieldCheck } from 'lucide-react';
import Link from 'next/link';

const NAV = [
  { href: ADMIN_ROUTES.overview, label: 'Overview' },
  { href: ADMIN_ROUTES.reviews, label: 'Review queue' },
  { href: ADMIN_ROUTES.sellers, label: 'Sellers' },
  { href: ADMIN_ROUTES.appeals, label: 'Appeals' },
  { href: ADMIN_ROUTES.scoring, label: 'Scoring models' },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-dvh overflow-hidden">
      {/* Subtle: a reviewer reads evidence on this screen all day. */}
      <Ambient />

      <aside className="w-60 shrink-0 border-r border-border/70 bg-card/40 p-4 backdrop-blur-xl">
        <div className="flex items-center gap-2.5 px-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-brand to-brand-2">
            <ShieldCheck
              className="h-3.5 w-3.5 text-[hsl(var(--background))]"
              strokeWidth={2.5}
              aria-hidden="true"
            />
          </span>
          <p className="text-sm font-bold tracking-tight">Admin</p>
          <ThemeToggle className="ml-auto" />
        </div>

        <nav aria-label="Admin" className="mt-6 space-y-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      <div className="min-w-0 flex-1">
        <RequireStaff>{children}</RequireStaff>
      </div>
    </div>
  );
}
