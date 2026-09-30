'use client';

import { stagger, useInView, usePrefersReducedMotion } from '@/lib/motion';
import { LISTING_CATEGORY_LABELS, type ListingCategory } from '@trustlens/constants';
import { cn } from '@trustlens/utils';
import { Grid2x2, Home, Laptop, Shirt, Smartphone, Wrench, type LucideIcon } from 'lucide-react';
import Link from 'next/link';
import { NAV_CATEGORIES } from '../nav-categories';

const ICON: Record<ListingCategory, LucideIcon> = {
  mobiles: Smartphone,
  electronics: Laptop,
  computers: Laptop,
  vehicles: Grid2x2,
  'vehicle-parts': Grid2x2,
  'property-sale': Home,
  'property-rent': Home,
  'home-appliances': Home,
  furniture: Home,
  fashion: Shirt,
  'books-hobbies': Grid2x2,
  animals: Grid2x2,
  services: Wrench,
  other: Grid2x2,
};

function Item({
  href,
  icon: Icon,
  label,
  muted,
  index,
  inView,
  reduced,
}: {
  href: string;
  icon: LucideIcon;
  label: string;
  muted?: boolean;
  index: number;
  inView: boolean;
  reduced: boolean;
}) {
  return (
    <Link
      href={href}
      style={inView && !reduced ? stagger(index, 45) : undefined}
      className={cn(
        'group flex flex-col items-center gap-1.5 rounded-lg px-3 py-2 text-center transition-transform duration-200 hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        !reduced && inView && 'animate-fade-up',
        !reduced && !inView && 'opacity-0',
      )}
    >
      <span
        className={cn(
          'grid h-11 w-11 place-items-center rounded-full transition-colors duration-200',
          muted
            ? 'bg-muted text-muted-foreground group-hover:bg-brand/10 group-hover:text-brand'
            : 'bg-brand/10 text-brand group-hover:bg-brand group-hover:text-[hsl(var(--background))]',
        )}
      >
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <span className="text-xs font-medium text-foreground">{label}</span>
    </Link>
  );
}

export function CategoryRow() {
  const { ref, inView } = useInView<HTMLDivElement>();
  const reduced = usePrefersReducedMotion();

  return (
    <section className="mx-auto max-w-7xl px-5 py-6 sm:px-8">
      <div
        ref={ref}
        className="flex flex-wrap items-center justify-center gap-2 rounded-xl border border-border bg-card p-3 shadow-sm sm:justify-between"
      >
        {NAV_CATEGORIES.map((category, index) => (
          <Item
            key={category}
            href={`/browse?category=${category}`}
            icon={ICON[category]}
            label={LISTING_CATEGORY_LABELS[category]}
            index={index}
            inView={inView}
            reduced={reduced}
          />
        ))}
        <Item
          href="/browse"
          icon={Grid2x2}
          label="More"
          muted
          index={NAV_CATEGORIES.length}
          inView={inView}
          reduced={reduced}
        />
      </div>
    </section>
  );
}
