/** Reusable UI rendering and interaction component: CategoryRow. */
'use client';
import Link from 'next/link';
import { useBrowseContext } from '@/features/marketplace';
import Image from 'next/image';
import { useLocale } from 'next-intl';
import { MARKETPLACE_ROOTS, categoryBrowseHref } from '@trustlens/constants';

export function CategoryRow() {
  const ur = useLocale() === 'ur';
  const context = useBrowseContext();
  return (
    <section aria-labelledby="explore-categories" className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
      <h2 id="explore-categories" className="mb-5 text-xl font-semibold">
        {ur ? 'اقسام دریافت کریں' : 'Explore categories'}
      </h2>
      <div className="grid grid-cols-3 gap-x-3 gap-y-6 sm:grid-cols-4 lg:grid-cols-7">
        {MARKETPLACE_ROOTS.map((node) => (
          <Link
            key={node.id}
            href={context.href(categoryBrowseHref(node.id))}
            className="tl-interactive group flex min-w-0 flex-col items-center gap-3 rounded-2xl p-2 text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="grid h-20 w-20 place-items-center rounded-full border border-border/60 bg-muted/40 sm:h-24 sm:w-24">
              <Image
                src={`/images/categories/${node.id}.webp`}
                width={96}
                height={96}
                alt=""
                sizes="(max-width: 639px) 80px, 96px"
                className="tl-category-picture h-20 w-20 object-contain sm:h-24 sm:w-24"
              />
            </span>
            <span className="text-xs font-medium leading-5 group-hover:text-brand sm:text-sm">
              {ur ? node.labelUr : node.label}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
