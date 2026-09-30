import { ExternalLink, ShieldCheck } from 'lucide-react';
import { getTranslations } from 'next-intl/server';
import Link from 'next/link';

export async function SafetyBanner() {
  const t = await getTranslations('Home');

  return (
    <div className="border-y border-brand/20 bg-brand/5">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-2 px-5 py-3 text-center text-sm sm:flex-row sm:justify-center sm:gap-3 sm:px-8">
        <ShieldCheck className="h-4 w-4 shrink-0 animate-pulse text-brand" aria-hidden="true" />
        <span className="font-medium">{t('safetyReminder')}</span>
        <span className="hidden text-muted-foreground sm:inline">{t('safetyFirst')}</span>
        <Link
          href="/safety"
          className="group inline-flex items-center gap-1 font-medium text-primary underline-offset-4 transition-colors hover:text-brand hover:underline"
        >
          {t('safetyTips')}
          <ExternalLink
            className="h-3 w-3 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
            aria-hidden="true"
          />
        </Link>
      </div>
    </div>
  );
}
