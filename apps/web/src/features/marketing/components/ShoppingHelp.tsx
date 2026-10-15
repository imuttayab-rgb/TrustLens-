/** Reusable UI rendering and interaction component: ShoppingHelp. */
'use client';
import { askAssistant } from '@/features/assistant';
import { ArrowRight, Sparkles } from 'lucide-react';
import { useLocale } from 'next-intl';
export function ShoppingHelp() {
  const ur = useLocale() === 'ur';
  return (
    <section className="mx-auto max-w-7xl px-5 pb-12 pt-4 sm:px-8">
      <div className="flex flex-col gap-5 rounded-2xl bg-[#102d36] p-6 text-white sm:flex-row sm:items-center sm:justify-between sm:p-8">
        <div className="flex gap-4">
          <span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-white/10 text-emerald-300">
            <Sparkles className="h-6 w-6" />
          </span>
          <div>
            <h2 className="text-xl font-semibold tracking-tight">
              {ur ? 'کہاں سے شروع کریں؟' : 'Not sure where to start?'}
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              {ur
                ? 'اپنا بجٹ اور ضرورت بتائیں۔ مناسب آپشنز ڈھونڈنے میں مدد لیں۔'
                : 'Tell us your budget. Let’s narrow it down.'}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => askAssistant()}
          className="inline-flex shrink-0 items-center justify-center gap-3 rounded-xl bg-emerald-300 px-5 py-3 text-sm font-semibold text-[#102d36] transition-colors hover:bg-emerald-200"
        >
          {ur ? 'ٹرسٹ لینس سے پوچھیں' : 'Ask TrustLens'}
          <ArrowRight className="h-4 w-4 rtl:rotate-180" />
        </button>
      </div>
    </section>
  );
}
