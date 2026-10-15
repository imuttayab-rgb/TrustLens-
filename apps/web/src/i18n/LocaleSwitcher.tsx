/** Localeswitcher module; defines LocaleSwitcher. */
'use client';

import { cn } from '@trustlens/utils';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useTransition } from 'react';
import { setLocaleAction } from './actions';
import { LOCALES, LOCALE_LABELS } from './config';

/**
 * Two locales only, so a toggle pair reads faster than a dropdown. Setting
 * the cookie doesn't itself re-render server components - `router.refresh()`
 * does that, the same trick a cookie-driven theme switch would need.
 */
export function LocaleSwitcher({ className }: { className?: string }) {
  const locale = useLocale();
  const t = useTranslations('Common');
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  return (
    <div
      role="group"
      aria-label={t('language')}
      className={cn('flex items-center gap-0.5 rounded-md border border-border p-0.5', className)}
    >
      {LOCALES.map((option) => (
        <button
          key={option}
          type="button"
          disabled={pending}
          aria-pressed={locale === option}
          onClick={() => {
            if (option === locale) return;
            startTransition(async () => {
              await setLocaleAction(option);
              router.refresh();
            });
          }}
          className={cn(
            'rounded-[5px] px-2 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            locale === option
              ? 'bg-brand text-[hsl(var(--background))]'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {LOCALE_LABELS[option]}
        </button>
      ))}
    </div>
  );
}
