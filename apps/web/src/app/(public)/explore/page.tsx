/** Next.js route/layout composition for (public)/explore: page. */
import type { Metadata } from 'next';
import Link from 'next/link';
import { getLocale } from 'next-intl/server';
import { CategoryListingRows } from '@/features/marketing';

export const metadata: Metadata = {
  title: 'Explore listings by category',
  description:
    'Explore live TrustLens listings by category, from mobile phones and cars to homes, services and everyday essentials.',
};

export default async function ExplorePage() {
  const ur = (await getLocale()) === 'ur';
  return (
    <div className="py-6 sm:py-8">
      <div className="mx-auto max-w-7xl px-4 sm:px-8">
        <nav
          aria-label={ur ? 'راستہ' : 'Breadcrumb'}
          className="mb-3 flex gap-2 text-sm text-muted-foreground"
        >
          <Link href="/" className="hover:text-brand">
            {ur ? 'ہوم' : 'Home'}
          </Link>
          <span aria-hidden="true">/</span>
          <span>{ur ? 'اشتہارات دیکھیں' : 'Explore listings'}</span>
        </nav>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          {ur ? 'ہر قسم کے اشتہارات دیکھیں' : 'Explore listings by category'}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {ur
            ? 'ہر قطار میں تازہ اشتہارات۔ کسی قسم کے تمام نتائج کے لیے مزید دیکھیں دبائیں۔'
            : 'Fresh listings in each category. Choose View more to see all results and filters.'}
        </p>
      </div>
      <CategoryListingRows />
    </div>
  );
}
