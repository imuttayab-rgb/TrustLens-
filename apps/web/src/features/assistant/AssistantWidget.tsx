/** Assistantwidget module; defines AssistantWidget. */
'use client';
import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useLocale } from 'next-intl';
import { Sparkles } from 'lucide-react';
const ChatPanel = dynamic(() => import('./ChatPanel'), { ssr: false });

export function AssistantWidget() {
  const ur = useLocale() === 'ur';
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [prompt, setPrompt] = useState({ text: '', sequence: 0 });
  useEffect(() => {
    function show(event: Event) {
      const text = (event as CustomEvent<{ message?: string }>).detail?.message ?? '';
      setLoaded(true);
      setOpen(true);
      setPrompt((previous) => ({ text, sequence: previous.sequence + 1 }));
    }
    window.addEventListener('trustlens:ask', show);
    return () => window.removeEventListener('trustlens:ask', show);
  }, []);
  return (
    <>
      <button
        type="button"
        onClick={() => {
          setLoaded(true);
          setOpen(true);
        }}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={ur ? 'ٹرسٹ لینس اسسٹنٹ کھولیں' : 'Open TrustLens assistant'}
        className="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center gap-2.5 rounded-full border border-white/20 bg-primary px-0 font-semibold text-primary-foreground shadow-[0_8px_32px_hsl(var(--brand)/0.3)] transition-transform hover:-translate-y-1 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/40 motion-reduce:transform-none sm:w-auto sm:px-5 print:hidden"
      >
        <Sparkles className="h-5 w-5" aria-hidden="true" />
        <span className="hidden text-sm sm:inline">{ur ? 'AI سے پوچھیں' : 'Ask TrustLens'}</span>
      </button>
      {loaded && <ChatPanel open={open} onClose={() => setOpen(false)} prompt={prompt} />}
    </>
  );
}
