/** Reusable UI rendering and interaction component: NotificationBell. */
'use client';

import { cn, formatRelative } from '@trustlens/utils';
import { Bell } from 'lucide-react';
import Link from 'next/link';
import { useLocale } from 'next-intl';
import { usePathname } from 'next/navigation';
import styles from './NotificationBell.module.css';
import { useEffect, useId, useRef, useState } from 'react';
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
      return conversationId ? `/messages/${conversationId}` : null;
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

export function NotificationBell({
  variant = 'icon',
  label,
}: {
  variant?: 'icon' | 'header';
  label?: string;
}) {
  const isUrdu = useLocale() === 'ur';
  const title = label ?? (isUrdu ? 'اطلاعات' : 'Notifications');
  const { data, isLoading, isError, refetch } = useNotifications();
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const pathname = usePathname();
  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(event: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onEscape(event: KeyboardEvent) {
      if (event.key === 'Escape' && panelRef.current?.contains(document.activeElement)) {
        setOpen(false);
        trigger.current?.focus();
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    document.addEventListener('keydown', onEscape);
    return () => {
      document.removeEventListener('mousedown', onClickOutside);
      document.removeEventListener('keydown', onEscape);
    };
  }, [open]);

  const unreadCount = data?.unreadCount ?? 0;
  const items = data?.items ?? [];

  return (
    <div
      ref={panelRef}
      className={styles.root}
      onBlur={(event) => {
        if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget))
          setOpen(false);
      }}
    >
      <button
        ref={trigger}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={unreadCount > 0 ? `${title}: ${unreadCount}` : title}
        aria-expanded={open}
        aria-controls={id}
        className={cn(styles.trigger, variant === 'header' && styles.headerTrigger)}
      >
        <Bell aria-hidden="true" />
        {variant === 'header' && <span>{title}</span>}
        {unreadCount > 0 && (
          <span className={styles.badge}>{unreadCount > 9 ? '9+' : unreadCount}</span>
        )}
      </button>

      {open && (
        <div id={id} role="region" aria-label={title} className={styles.panel}>
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <p className="text-sm font-medium">{title}</p>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => markAllRead.mutate()}
                disabled={markAllRead.isPending}
                className="text-xs text-primary hover:underline disabled:opacity-50"
              >
                {isUrdu ? 'سب پڑھی ہوئی نشان زد کریں' : 'Mark all read'}
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {isLoading ? (
              <p role="status" className="px-3 py-6 text-center text-sm">
                {isUrdu ? 'لوڈ ہو رہا ہے…' : 'Loading notifications…'}
              </p>
            ) : isError ? (
              <div className="px-3 py-6 text-center text-sm">
                <p role="alert">
                  {isUrdu ? 'اطلاعات لوڈ نہیں ہو سکیں۔' : 'Could not load notifications.'}
                </p>
                <button
                  type="button"
                  className="mt-2 text-primary underline"
                  onClick={() => void refetch()}
                >
                  {isUrdu ? 'دوبارہ کوشش کریں' : 'Try again'}
                </button>
              </div>
            ) : items.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                {isUrdu ? 'ابھی کوئی اطلاع نہیں۔' : 'Nothing yet.'}
              </p>
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
                    className="block w-full text-start"
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
