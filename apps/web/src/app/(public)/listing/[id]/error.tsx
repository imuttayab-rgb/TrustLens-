/** Next.js route/layout composition for (public)/listing/[id]: error. */
'use client';
import { useLocale } from 'next-intl';
export default function ListingError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const ur = useLocale() === 'ur';
  return (
    <main className="mx-auto max-w-xl px-5 py-16 text-center">
      <h1 className="text-2xl font-semibold">
        {ur ? 'اشتہار لوڈ نہیں ہو سکا' : 'We could not load this listing'}
      </h1>
      <p className="mt-3 text-muted-foreground">
        {ur
          ? 'سروس ابھی دستیاب نہیں۔ دوبارہ کوشش کریں۔'
          : 'The service is temporarily unavailable. Please try again.'}
      </p>
      <button
        onClick={reset}
        className="mt-6 rounded-lg bg-primary px-5 py-3 text-primary-foreground"
      >
        {ur ? 'دوبارہ کوشش' : 'Try again'}
      </button>
    </main>
  );
}
