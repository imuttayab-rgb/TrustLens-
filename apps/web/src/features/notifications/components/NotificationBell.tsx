'use client';

import { cn, formatRelative } from '@trustlens/utils';
import { Bell } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  type AppNotification,
} from '../hooks/use-notifications';

/** Where a notification's "open it" click should go, based on its type and
 * the ids it carries - mirrors the routes the message thread and handover
 * page already use, not a new screen of its own. */
function linkFor(notification: AppNotification): string | null {
  const { conversationId, transactionId, reportId } = notification.data;
  switch (notification.type) {
    case 'MESSAGE_RECEIVED':
    case 'OFFER_RECEIVED':
    case 'OFFER_ACCEPTED':
    case 'OFFER_REJECTED':
    case 'MEETUP_PROPOSED':
    case 'MEETUP_ACCEPTED':
    case 'MEETUP_DECLINED':
      return conversationId ? `/dashboard/messages/${conversationId}` : null;
    case 'HANDOVER_CONFIRMED':
    case 'TRANSACTION_COMPLETED':
    case 'TRANSACTION_CANCELLED':
      return transactionId ? `/dashboard/handover/${transactionId}` : null;
    case 'REPORT_RESOLVED':
      return reportId ? '/dashboard/reports' : null;
    default:
      return null;
  }
}

export function NotificationBell() {
  const { data } = useNotifications();
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(event: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [open]);

  const unreadCount = data?.unreadCount ?? 0;
  const items = data?.items ?? [];

  return (
    <div ref={panelRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={unreadCount > 0 ? `${unreadCount} unread notifications` : 'Notifications'}
        aria-expanded={open}
        className="relative grid h-9 w-9 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Bell className="h-4 w-4" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="bg-popover absolute right-0 z-30 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-lg border border-border shadow-lg">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <p className="text-sm font-medium">Notifications</p>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => markAllRead.mutate()}
                disabled={markAllRead.isPending}
                className="text-xs text-primary hover:underline disabled:opacity-50"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">Nothing yet.</p>
            ) : (
              items.map((notification) => {
                const href = linkFor(notification);
                const unread = notification.readAt === null;
                const content = (
                  <div
                    className={cn(
                      'space-y-0.5 px-3 py-2.5 text-sm transition-colors hover:bg-muted/50',
                      unread && 'bg-primary/5',
                    )}
                  >
                    <p className="flex items-center gap-1.5 font-medium">
                      {unread && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />}
                      {notification.title}
                    </p>
                    <p className="truncate text-muted-foreground">{notification.body}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatRelative(notification.createdAt)}
                    </p>
                  </div>
                );

                function handleOpen() {
                  if (unread) markRead.mutate(notification.id);
                  setOpen(false);
                }

                return href ? (
                  <Link key={notification.id} href={href} onClick={handleOpen}>
                    {content}
                  </Link>
                ) : (
                  <button
                    key={notification.id}
                    type="button"
                    onClick={handleOpen}
                    className="block w-full text-left"
                  >
                    {content}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
