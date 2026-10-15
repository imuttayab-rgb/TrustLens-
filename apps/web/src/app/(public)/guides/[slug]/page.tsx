/** Next.js route/layout composition for (public)/guides/[slug]: page. */
import { GUIDES } from '@/features/guides';
import { getLocale } from 'next-intl/server';
import { notFound } from 'next/navigation';
import Link from 'next/link';
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const guide = GUIDES.find((g) => g.slug === slug);
  return { title: guide ? `${guide.title[0]} · TrustLens` : 'Guide not found' };
}
export default async function GuidePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const g = GUIDES.find((g) => g.slug === slug);
  if (!g) notFound();
  const ur = (await getLocale()) === 'ur';
  const i = ur ? 1 : 0;
  return (
    <article className="mx-auto max-w-3xl px-5 py-10">
      <Link href="/guides" className="text-sm text-brand hover:underline">
        {ur ? 'تمام رہنمائی ←' : '← All guides'}
      </Link>
      <p className="mt-6 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        TrustLens · {ur ? 'رہنمائی' : 'Guides'}
      </p>
      <h1 className="mt-3 text-3xl font-semibold leading-tight sm:text-4xl">{g.title[i]}</h1>
      <p className="mt-5 text-lg leading-8 text-muted-foreground">{g.intro[i]}</p>
      <div className="mt-8 space-y-8">
        {g.sections.map((s, k) => (
          <section key={k}>
            <h2 className="text-xl font-semibold">{s.heading[i]}</h2>
            <p className="mt-3 text-base leading-8 text-muted-foreground">{s.body[i]}</p>
          </section>
        ))}
      </div>
      <nav className="mt-10 flex flex-wrap gap-4 border-t border-border pt-6">
        <Link
          href={
            g.category === 'motors'
              ? '/motors'
              : g.category === 'property'
                ? '/property'
                : '/browse'
          }
          className="rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground"
        >
          {ur ? 'اشتہارات دیکھیں' : 'Explore listings'}
        </Link>
        <Link
          href="/dashboard/listings/new"
          className="rounded-xl border border-border px-5 py-3 text-sm"
        >
          {ur ? 'اشتہار دیں' : 'Post an ad'}
        </Link>
      </nav>
    </article>
  );
}
