/** Support, forwarding and dialog form views used by the chat surface. */
'use client';
import { profileRequest } from '@/features/profile';
import { X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useConversations, useSendMessage, type Message } from '../hooks/use-messaging';

export function ChatDialog({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      onCancel={onClose}
      aria-label={title}
      className="w-[min(94vw,460px)] rounded-xl border border-border bg-background p-5 text-foreground shadow-xl backdrop:bg-black/40"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold">{title}</h2>
        <button type="button" aria-label="Close dialog" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function SupportDialog({
  conversationId,
  message,
  onClose,
}: {
  conversationId: string;
  message: Message | null;
  onClose: () => void;
}) {
  const [description, setDescription] = useState('');
  const [reason, setReason] = useState('other');
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <ChatDialog title="Report issue / support" onClose={onClose}>
      {result ? (
        <p role="status" className="mt-4 text-sm">
          Your support case was submitted. Reference: <strong>{result}</strong>. You can track it in
          your reports.
        </p>
      ) : (
        <form
          className="mt-4 space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            setBusy(true);
            setError(null);
            void profileRequest<{ reportId: string }>(
              `/me/conversations/${conversationId}/support`,
              {
                method: 'POST',
                body: JSON.stringify({ description, reason, messageId: message?.id ?? null }),
              },
            )
              .then((data) => setResult(data.reportId))
              .catch((e) => setError(e instanceof Error ? e.message : 'Could not submit.'))
              .finally(() => setBusy(false));
          }}
        >
          <label className="block text-sm">
            Issue
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mt-1 w-full rounded border border-input bg-background p-2"
            >
              <option value="other">Other issue</option>
              <option value="sensitive_information">Sensitive personal information</option>
              <option value="delivery_issue">Delivery / product issue</option>
              <option value="harassment">Harassment</option>
            </select>
          </label>
          <label className="block text-sm">
            Describe what happened
            <textarea
              required
              minLength={10}
              maxLength={4000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="mt-1 w-full rounded border border-input bg-background p-2"
            />
          </label>
          <p className="text-xs text-muted-foreground">
            Authorized support staff can review retained conversation records for this case.
          </p>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <button
            disabled={busy || description.trim().length < 10}
            className="rounded bg-brand px-4 py-2 text-sm text-white disabled:opacity-40"
          >
            {busy ? 'Submitting…' : 'Submit issue'}
          </button>
        </form>
      )}
    </ChatDialog>
  );
}
export function ForwardDialog({ message, onClose }: { message: Message; onClose: () => void }) {
  const [q, setQ] = useState('');
  const { data } = useConversations({ q, limit: 50 });
  const send = useSendMessage();
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState('');
  const id = useRef(crypto.randomUUID());
  return (
    <ChatDialog title="Forward message" onClose={onClose}>
      <p className="mt-3 text-xs text-muted-foreground">
        Choose a conversation. The destination must still allow messages.
      </p>
      <input
        aria-label="Search conversations"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search name or product"
        className="my-3 w-full rounded border border-input bg-background p-2 text-sm"
      />
      <select
        aria-label="Destination conversation"
        value={selected}
        onChange={(e) => {
          setSelected(e.target.value);
          id.current = crypto.randomUUID();
        }}
        className="w-full rounded border border-input bg-background p-2 text-sm"
      >
        <option value="">Select a conversation</option>
        {data?.items.map((item) => (
          <option key={item.id} value={item.id}>
            {item.counterpartName} · {item.listingTitle ?? 'Chat'}
          </option>
        ))}
      </select>
      {error && (
        <p role="alert" className="my-2 text-sm text-destructive">
          {error}
        </p>
      )}
      <button
        disabled={!selected || send.isPending}
        onClick={() => {
          setError(null);
          void send
            .mutateAsync({
              body: '',
              conversationId: selected,
              forwardId: message.id,
              clientId: id.current,
            })
            .then(onClose)
            .catch((e) => setError(e instanceof Error ? e.message : 'Could not forward.'));
        }}
        className="mt-4 rounded bg-brand px-4 py-2 text-sm text-white disabled:opacity-40"
      >
        Forward
      </button>
    </ChatDialog>
  );
}
