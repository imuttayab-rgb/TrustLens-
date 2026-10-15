/** Adassistant module; defines AdSpec, AdContent, AdUndo, AdAssistant. */
'use client';

import { useEffect, useRef, useState } from 'react';
import { categoryNode } from '@trustlens/constants';
import { useLocale } from 'next-intl';
import { Loader2, Sparkles, Undo2 } from 'lucide-react';
import { assistantApi, EnhancementError, type Enhancement } from './api';

export type AdSpec = { key: string; value: string };
export interface AdContent {
  description: string;
  specs: AdSpec[];
}
export interface AdUndo {
  before: AdContent;
  after: AdContent;
}
interface Props extends AdContent {
  title: string;
  category: string;
  categoryNodeId?: string | null;
  condition: string;
  listingId: string | null;
  photoRevision: string;
  undo: AdUndo | null;
  onReplace: (next: AdContent) => AdContent;
  onUndo: () => void;
  disabled?: boolean;
}

/** Explicit click only. The existing textarea is the sole seller input. */
export function AdAssistant({
  title,
  category,
  categoryNodeId = null,
  condition,
  description,
  specs,
  listingId,
  photoRevision,
  undo,
  onReplace,
  onUndo,
  disabled = false,
}: Props) {
  const ur = useLocale() === 'ur';
  const [language, setLanguage] = useState<'en' | 'ur' | 'roman-ur'>(ur ? 'ur' : 'en');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Enhancement | null>(null);
  const [retryAt, setRetryAt] = useState(0);
  const [now, setNow] = useState(0);
  const controller = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const signature = JSON.stringify({
    title,
    category,
    categoryNodeId,
    condition,
    description,
    specs,
    listingId,
    photoRevision,
    language,
  });
  const appliedSignature = useRef<string | null>(null);
  const latest = useRef(signature);
  latest.current = signature;
  const cooldown = Math.max(0, Math.ceil((retryAt - now) / 1000));
  const canUndo =
    undo !== null && JSON.stringify(undo.after) === JSON.stringify({ description, specs });
  const ready =
    title.trim().length >= 3 &&
    Boolean(category) &&
    ((categoryNodeId && !categoryNode(categoryNodeId)?.conditionRequired) ||
      ['NEW', 'LIKE_NEW', 'USED', 'FOR_PARTS'].includes(condition));

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      controller.current?.abort();
      controller.current = null;
    };
  }, []);
  useEffect(() => {
    if (!retryAt) return;
    setNow(Date.now());
    const timer = window.setInterval(() => {
      const timestamp = Date.now();
      setNow(timestamp);
      if (timestamp >= retryAt) {
        setRetryAt(0);
        window.clearInterval(timer);
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [retryAt]);
  useEffect(() => {
    if (controller.current) {
      controller.current.abort();
      controller.current = null;
      setBusy(false);
      setError(
        ur
          ? 'تفصیلات بدل گئی ہیں۔ نئی تفصیلات کے ساتھ دوبارہ کلک کریں۔'
          : disabled
            ? 'AI stopped while the listing was saved. Your text and features are unchanged.'
            : 'Your details changed. Click again to enhance the latest version.',
      );
    }
    if (appliedSignature.current !== signature) setResult(null);
  }, [signature, ur, disabled]);

  async function replace() {
    // The ref also blocks a rapid second click before React renders disabled=true.
    if (!ready || disabled || controller.current || Date.now() < retryAt) return;
    const abort = new AbortController();
    controller.current = abort;
    const original = signature;
    setBusy(true);
    setError('');
    setResult(null);
    let timedOut = false;
    const timer = window.setTimeout(() => {
      timedOut = true;
      abort.abort();
    }, 95000);
    try {
      const data = await assistantApi.enhance(
        {
          title: title.trim().slice(0, 80),
          category,
          categoryNodeId,
          condition: (condition || null) as 'NEW' | 'LIKE_NEW' | 'USED' | 'FOR_PARTS' | null,
          description,
          notes: '',
          facts: Object.fromEntries(
            specs
              .filter((x) => x.key.trim() && x.value.trim())
              .map((x) => [x.key.trim(), x.value.trim()]),
          ),
          listingId,
          usePhotos: true,
          language,
        },
        abort.signal,
      );
      if (!mounted.current || abort.signal.aborted || latest.current !== original) return;
      // Clear before the atomic replacement changes the input signature.
      controller.current = null;
      const applied = onReplace({ description: data.description, specs: data.specs });
      appliedSignature.current = JSON.stringify({
        ...JSON.parse(original),
        description: applied.description,
        specs: applied.specs,
      });
      setResult(data);
    } catch (e) {
      if (!mounted.current || latest.current !== original || (!timedOut && abort.signal.aborted))
        return;
      if (e instanceof EnhancementError && e.retryAfter) {
        const timestamp = Date.now();
        setNow(timestamp);
        setRetryAt(timestamp + e.retryAfter * 1000);
      }
      setError(
        timedOut
          ? 'AI took too long. Your description and features are unchanged. Try again when ready.'
          : e instanceof Error
            ? e.message
            : 'AI could not finish. Your description and features are unchanged.',
      );
    } finally {
      window.clearTimeout(timer);
      if (controller.current === abort) controller.current = null;
      if (mounted.current && latest.current === original) setBusy(false);
      // A successful replacement changes signature; clear busy here too.
      if (mounted.current && !controller.current) setBusy(false);
    }
  }

  return (
    <div className="space-y-2 font-normal" aria-busy={busy}>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => void replace()}
          disabled={!ready || disabled || busy || cooldown > 0}
          className="flex items-center gap-1.5 rounded-lg border border-brand/30 px-3 py-2 text-xs font-semibold text-brand disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {busy
            ? ur
              ? 'تیار ہو رہا ہے…'
              : 'Enhancing…'
            : cooldown > 0
              ? `Try again in ${cooldown}s`
              : 'Replace with AI'}
        </button>
        <select
          aria-label="AI description language"
          value={language}
          disabled={busy || disabled}
          onChange={(e) => setLanguage(e.target.value as typeof language)}
          className="h-8 rounded-md border border-input bg-card px-2 text-xs"
        >
          <option value="en">English</option>
          <option value="roman-ur">Roman Urdu</option>
          <option value="ur">اردو</option>
        </select>
        {canUndo && (
          <button
            type="button"
            disabled={busy || disabled}
            onClick={() => {
              onUndo();
              setResult(null);
              setError('');
            }}
            className="flex items-center gap-1 text-xs text-brand disabled:opacity-50"
          >
            <Undo2 className="h-3.5 w-3.5" aria-hidden="true" />
            Undo
          </button>
        )}
      </div>
      {!ready && (
        <p className="text-xs text-muted-foreground">
          Choose a title, category and condition first.
        </p>
      )}
      <p className="text-[11px] leading-5 text-muted-foreground">
        {ur
          ? 'اپنی تفصیل اوپر لکھیں۔ AI اسی متن اور پروڈکٹ کی تفصیلات کو بہتر کرے گا۔'
          : 'Uses your description, product details and up to two uploaded photos. Review the result before publishing.'}
      </p>
      {busy && (
        <p role="status" className="text-xs text-muted-foreground">
          Checking details and preparing your description…
        </p>
      )}
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
      {result && (
        <div role="status" className="space-y-1 text-xs leading-5 text-muted-foreground">
          <p className="text-brand">
            Description and features updated. You can edit them before publishing.
          </p>
          {result.warnings.map((warning, i) => (
            <p key={i}>{warning}</p>
          ))}
          {result.missingDetails.length > 0 && (
            <p>Consider adding: {result.missingDetails.join(' · ')}</p>
          )}
          {result.photoHints.length > 0 && (
            <p>Photo suggestions — confirm before adding: {result.photoHints.join(' · ')}</p>
          )}
          {result.sources.length > 0 && (
            <details>
              <summary className="cursor-pointer">Specification sources</summary>
              {result.sources.map((source) => (
                <a
                  key={source.id}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-brand underline"
                >
                  {source.title}
                </a>
              ))}
            </details>
          )}
        </div>
      )}
    </div>
  );
}
