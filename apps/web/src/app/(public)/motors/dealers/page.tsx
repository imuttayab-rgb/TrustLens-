/** Next.js route/layout composition for (public)/motors/dealers: page. */
import { Dealers } from '@/features/marketplace';
import { getLocale } from 'next-intl/server';
import Link from 'next/link';
export const metadata = { title: 'Motor dealer directory · TrustLens' };
export default async function DealerPage() {
  const ur = (await getLocale()) === 'ur';
  return (
    <div className="mx-auto max-w-7xl px-5 py-8">
      <Link href="/motors" className="text-sm text-brand">
        {ur ? 'موٹرز پر واپس' : '← Back to Motors'}
      </Link>
      <h1 className="mt-5 text-3xl font-semibold">
        {ur ? 'موٹرز ڈیلرز' : 'Motor dealer directory'}
      </h1>
      <Dealers directory />
    </div>
  );
}
