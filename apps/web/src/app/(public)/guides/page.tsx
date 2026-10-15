/** Next.js route/layout composition for (public)/guides: page. */
import { GuideCards } from '@/features/guides';
import { getLocale } from 'next-intl/server';
export const metadata = {
  title: 'Marketplace guides · TrustLens',
  description:
    'Practical guides to comparing listings and writing clear, accurate ads on TrustLens.',
};
export default async function GuidesPage() {
  const ur = (await getLocale()) === 'ur';
  return (
    <div className="mx-auto max-w-7xl px-5 py-10">
      <h1 className="text-3xl font-semibold">
        {ur ? 'بہتر اشتہار، واضح انتخاب' : 'Better listings. Clearer choices.'}
      </h1>
      <p className="mt-3 max-w-2xl text-muted-foreground">
        {ur
          ? 'ٹرسٹ لینس کے استعمال، اشتہار کی تفصیل اور متعلقہ تلاش کے بارے میں رہنمائی۔'
          : 'Learn how to compare details, use marketplace features and keep your own ads accurate.'}
      </p>
      <GuideCards />
    </div>
  );
}
