/** Chat rendering. Side effects and business actions are in useChatController. */
'use client';
import { cn, formatRelative } from '@trustlens/utils';
import { Check, CheckCheck, Phone, Send, ShieldAlert, X } from 'lucide-react';
import { assessMessageRisk, hasRiskFlags } from '../lib/risk-heuristics';
import { CallHistory, CallNotifications } from './VoiceCalls';
import { VoiceMessage } from './VoicePlayback';
import { VoiceRecorder } from './VoiceRecorder';

import { ChatDialog, ForwardDialog, SupportDialog } from './ChatDialogs';

import { useChatController, type ChatOptions } from '../hooks/use-chat-controller';
export function ChatExperience(options: ChatOptions) {
  const { conversation, userId, profileReady } = options;
  const {
    canSend,
    calls,
    busy,
    recording,
    clear,
    setReport,
    closure,
    closed,
    remaining,
    undo,
    now,
    undoClear,
    scroll,
    nearBottom,
    query,
    messages,
    setReply,
    setForward,
    setEditing,
    setEditBody,
    deleteMessage,
    bottom,
    error,
    reply,
    sendText,
    draft,
    setDraft,
    send,
    setRecording,
    refresh,
    editing,
    saveEdit,
    editBody,
    report,
    forward,
  } = useChatController(options);
  return (
    <>
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2 text-xs">
        <button
          type="button"
          aria-label="Start voice call"
          disabled={!canSend || !calls.available || calls.busy || recording}
          onClick={() => void calls.start(conversation.id)}
          className="flex items-center gap-1 rounded border border-border px-2 py-1 disabled:opacity-40"
        >
          <Phone size={14} />
          Voice call
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void clear()}
          className="rounded border border-border px-2 py-1"
        >
          Clear my chat
        </button>
        <button
          type="button"
          onClick={() => setReport('chat')}
          className="rounded border border-border px-2 py-1"
        >
          Report issue / support
        </button>
        <CallNotifications />
        <span className="ml-auto text-muted-foreground">Edit / delete for everyone: 1 minute</span>
      </div>
      <CallHistory conversationId={conversation.id} />
      {(closure || conversation.blocked || closed) && (
        <div className="border-b border-border bg-muted/50 px-4 py-3 text-xs" role="status">
          {closed ? (
            'Chat closed. You can read old messages, play voice messages and contact support.'
          ) : conversation.blocked ? (
            'Messaging is blocked. Your previous messages remain available.'
          ) : (
            <>
              <strong>
                {conversation.listingStatus === 'SOLD' ? 'Product sold' : 'Product inactive'}
              </strong>{' '}
              · Chat closes in {Math.floor(remaining / 3600000)}h{' '}
              {Math.floor(remaining / 60000) % 60}m.
              <br />
              Closing time: {new Date(closure as number).toLocaleString()}
              {remaining <= 86400000 && (
                <span className="mt-1 block font-medium">
                  Reminder: less than 24 hours remain to finish this conversation.
                </span>
              )}
            </>
          )}
        </div>
      )}
      {undo && now < Date.parse(undo.undoUntil) && (
        <div className="flex items-center justify-between bg-muted px-4 py-2 text-sm" role="status">
          Your history was cleared.
          <button
            disabled={busy}
            className="font-semibold text-brand underline"
            onClick={() => void undoClear()}
          >
            Undo ({Math.ceil((Date.parse(undo.undoUntil) - now) / 1000)}s)
          </button>
        </div>
      )}
      <div
        ref={scroll}
        onScroll={() => {
          const node = scroll.current;
          if (node)
            nearBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 100;
        }}
        className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4 pb-20"
        aria-label="Chat messages"
      >
        {query.hasNextPage && (
          <button
            type="button"
            disabled={query.isFetchingNextPage}
            onClick={() => {
              const node = scroll.current;
              const height = node?.scrollHeight ?? 0;
              nearBottom.current = false;
              void query.fetchNextPage().then(() =>
                requestAnimationFrame(() => {
                  if (node) node.scrollTop += node.scrollHeight - height;
                }),
              );
            }}
            className="mx-auto block rounded border border-border px-3 py-2 text-xs"
          >
            {query.isFetchingNextPage ? 'Loading…' : 'Load earlier messages'}
          </button>
        )}
        {query.isPending && <p className="py-6 text-center text-sm">Loading messages…</p>}
        {query.isError && (
          <p className="text-sm text-destructive">
            Could not load messages.{' '}
            <button onClick={() => void query.refetch()} className="underline">
              Retry
            </button>
          </p>
        )}
        {!query.isPending && !query.isError && !messages.length && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No messages in your current chat history.
          </p>
        )}
        {messages.map((message, index) => {
          const mine = message.senderId === userId;
          const editable =
            mine &&
            !message.deleted &&
            now <
              Date.parse(
                message.editableUntil ??
                  new Date(Date.parse(message.createdAt) + 60000).toISOString(),
              );
          const risk = assessMessageRisk(message.deleted ? '' : message.body);
          const date = new Date(message.createdAt).toLocaleDateString();
          const previous = messages[index - 1];
          return (
            <div key={message.id}>
              {(!previous || new Date(previous.createdAt).toLocaleDateString() !== date) && (
                <p className="mb-4 text-center text-[11px] text-muted-foreground">{date}</p>
              )}
              <div className={cn('flex flex-col', mine ? 'items-end' : 'items-start')}>
                <div
                  className={cn(
                    'max-w-[88%] rounded-xl px-3 py-2 text-sm sm:max-w-[75%]',
                    mine ? 'bg-brand text-white' : 'bg-muted text-foreground',
                    message.deleted && 'italic opacity-70',
                  )}
                >
                  {message.forwarded && !message.deleted && (
                    <p className="mb-1 text-[10px] opacity-70">Forwarded</p>
                  )}
                  {message.replyTo && !message.deleted && (
                    <div className="mb-2 rounded border-l-2 border-current bg-black/10 p-2 text-xs">
                      {message.replyTo.body}
                    </div>
                  )}
                  {message.kind === 'voice' && !message.deleted ? (
                    <VoiceMessage message={message} queue={messages} />
                  ) : (
                    <p className="whitespace-pre-wrap break-words">{message.body}</p>
                  )}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1 text-[10px] text-muted-foreground">
                  <span title={new Date(message.createdAt).toLocaleString()}>
                    {formatRelative(message.createdAt)}
                  </span>
                  {message.editedAt && <span>· Edited</span>}
                  {mine && (
                    <>
                      <span aria-hidden="true">
                        {message.readAt ? <CheckCheck size={12} /> : <Check size={12} />}
                      </span>
                      <span>
                        {message.playedAt && message.kind === 'voice'
                          ? 'Played'
                          : message.readAt
                            ? 'Read'
                            : 'Sent'}
                      </span>
                    </>
                  )}
                </div>
                {!message.deleted && (
                  <div className="mt-1 flex flex-wrap justify-end gap-3 text-[11px] text-muted-foreground">
                    {canSend && (
                      <button onClick={() => setReply(message)} className="hover:underline">
                        Reply
                      </button>
                    )}
                    <button onClick={() => setForward(message)} className="hover:underline">
                      Forward
                    </button>
                    <button onClick={() => setReport(message)} className="hover:underline">
                      Report
                    </button>
                    {editable && (
                      <>
                        {message.kind !== 'voice' && (
                          <button
                            disabled={busy}
                            onClick={() => {
                              setEditing(message);
                              setEditBody(message.body);
                            }}
                            className="hover:underline"
                          >
                            Edit
                          </button>
                        )}
                        <button
                          disabled={busy}
                          onClick={() => {
                            if (
                              window.confirm(
                                'Delete this message for both users? Platform records are retained. Already viewed, heard or saved copies cannot be recalled.',
                              )
                            )
                              void deleteMessage(message);
                          }}
                          className="hover:underline"
                        >
                          Delete for everyone
                        </button>
                        <span>
                          {Math.max(
                            0,
                            Math.ceil((Date.parse(message.editableUntil ?? '') - now) / 1000),
                          )}
                          s
                        </span>
                      </>
                    )}
                  </div>
                )}
                {!mine && !message.deleted && hasRiskFlags(risk) && (
                  <p className="mt-2 flex max-w-[85%] items-start gap-2 rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
                    <ShieldAlert size={16} className="shrink-0" />
                    {risk.paymentPressure
                      ? 'Never pay in advance for an item you have not inspected. Keep your personal information private.'
                      : 'Check links carefully before opening them.'}
                  </p>
                )}
              </div>
            </div>
          );
        })}
        <div ref={bottom} />
      </div>
      {error && (
        <p role="alert" className="px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}
      {reply && canSend && (
        <div className="flex items-center gap-2 border-t border-border bg-muted/40 px-3 py-2 text-xs">
          <p className="min-w-0 flex-1 truncate">
            Replying to: {reply.kind === 'voice' ? 'Voice message' : reply.body}
          </p>
          <button aria-label="Cancel reply" onClick={() => setReply(null)}>
            <X size={16} />
          </button>
        </div>
      )}
      <div className="border-t border-border p-3">
        {
          <div className="flex flex-wrap items-end gap-2">
            <form
              className={!canSend || recording ? 'hidden' : 'flex min-w-0 flex-1 items-end gap-2'}
              onSubmit={(e) => {
                e.preventDefault();
                void sendText();
              }}
            >
              <textarea
                value={draft}
                maxLength={4000}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    void sendText();
                  }
                }}
                rows={1}
                aria-label="Message"
                placeholder="Type a message…"
                className="max-h-32 min-w-0 flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2.5 text-sm"
              />
              <button
                type="submit"
                aria-label="Send message"
                disabled={!draft.trim() || send.isPending}
                className="grid h-10 w-10 place-items-center rounded-full bg-brand text-white disabled:opacity-40"
              >
                <Send size={18} />
              </button>
            </form>
            <VoiceRecorder
              key={conversation.id}
              conversationId={conversation.id}
              disabled={!canSend || send.isPending || calls.busy}
              replyToId={reply?.id}
              onActivity={setRecording}
              onSent={() => {
                setReply(null);
                nearBottom.current = true;
                void refresh();
              }}
            />
          </div>
        }
        {!canSend && (
          <p className="text-center text-xs text-muted-foreground">
            {!profileReady
              ? 'Complete your verified profile to send messages.'
              : closed
                ? 'This conversation is read-only.'
                : 'You cannot send messages in this conversation.'}
          </p>
        )}
        <p className="mt-2 text-center text-[10px] text-muted-foreground">
          Messages remain on the platform for records and support. Clearing removes only your
          visible history.
        </p>
      </div>
      {editing && (
        <ChatDialog title="Edit message" onClose={() => setEditing(null)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void saveEdit();
            }}
          >
            <textarea
              aria-label="Edit message text"
              value={editBody}
              maxLength={4000}
              onChange={(e) => setEditBody(e.target.value)}
              className="mt-3 w-full rounded border border-input bg-background p-3"
              rows={4}
            />
            <p className="my-2 text-xs text-muted-foreground">
              The original 1-minute deadline still applies. An Edited label will appear.
            </p>
            <button
              disabled={busy || !editBody.trim()}
              className="rounded bg-brand px-4 py-2 text-sm text-white"
            >
              Save edit
            </button>
            {error && (
              <p role="alert" className="mt-2 text-sm text-destructive">
                {error}
              </p>
            )}
          </form>
        </ChatDialog>
      )}
      {report && (
        <SupportDialog
          conversationId={conversation.id}
          message={report === 'chat' ? null : report}
          onClose={() => setReport(null)}
        />
      )}
      {forward && <ForwardDialog message={forward} onClose={() => setForward(null)} />}
    </>
  );
}
