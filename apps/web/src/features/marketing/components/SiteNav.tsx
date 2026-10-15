/** Reusable UI rendering and interaction component: SiteNav. */
'use client';

import { useBrowseContext } from '@/features/marketplace';
import { AccountMenu } from './AccountMenu';
import { NotificationBell, useNotifications } from '@/features/notifications';
import { useSession } from '@/lib/auth/use-session';
import { Bell, CircleHelp, Heart, MessageCircle, Plus, ShieldCheck, UserRound } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Suspense } from 'react';
import { MegaMenu } from '@/features/categories';
import { HeaderPreferences } from './HeaderPreferences';
import { HeaderSearch, HeaderSearchFallback } from './HeaderSearch';
import styles from './BrowseNav.module.css';

/** One shared header; preferences and member shortcuts stay visible at every width. */
export function SiteNav() {
  return (
    <Suspense fallback={<div className="h-48 border-b border-border bg-card" aria-hidden="true" />}>
      <SiteNavContent />
    </Suspense>
  );
}
function SiteNavContent() {
  const context = useBrowseContext();
  const t = useTranslations('SiteNav');
  const tc = useTranslations('Common');
  const isUrdu = useLocale() === 'ur';
  const pathname = usePathname();
  const { data: session } = useSession();
  const { data: notifications } = useNotifications(Boolean(session));
  const unreadMessages = Boolean(
    session &&
    notifications?.items.some((item) => item.type === 'MESSAGE_RECEIVED' && item.readAt === null),
  );
  const active = (href: string) =>
    pathname === href || (href === '/' && ['/browse', '/explore'].includes(pathname));
  const notificationsLabel = isUrdu ? 'اطلاعات' : 'Notifications';
  return (
    <header className={styles.header} data-trustlens-header="open-v1">
      <div className={styles.utilityRow}>
        <div className={styles.utilityInner}>
          <nav className={styles.support} aria-label={isUrdu ? 'مدد اور حفاظت' : 'Help and safety'}>
            <Link href="/help">
              <CircleHelp aria-hidden="true" />
              {isUrdu ? 'مدد مرکز' : 'Help Centre'}
            </Link>
            <Link href="/safety">
              <ShieldCheck aria-hidden="true" />
              {isUrdu ? 'حفاظتی ہدایات' : 'Safety Tips'}
            </Link>
          </nav>
          <HeaderPreferences />
        </div>
      </div>
      <div className={styles.mainRow}>
        <Link href={context.href('/')} className={styles.logo} aria-label="TrustLens">
          <ShieldCheck aria-hidden="true" />
          <span>TrustLens</span>
        </Link>
        <nav className={styles.nav} aria-label={isUrdu ? 'مرکزی نیویگیشن' : 'Main navigation'}>
          <Link
            className={styles.navLink}
            href={context.href('/')}
            aria-current={active('/') ? 'page' : undefined}
          >
            {t('marketplace')}
          </Link>
          <Suspense fallback={<span className="text-sm">All categories</span>}>
            <MegaMenu />
          </Suspense>
          <Link
            className={styles.navLink}
            href="/check"
            aria-current={active('/check') ? 'page' : undefined}
          >
            {t('trustCheck')}
          </Link>
          <Link
            className={styles.navLink}
            href="/safety"
            aria-current={active('/safety') ? 'page' : undefined}
          >
            {t('safeMeet')}
          </Link>
          <Link
            className={styles.navLink}
            href={context.href('/motors')}
            aria-current={pathname === '/motors' ? 'page' : undefined}
          >
            {isUrdu ? 'موٹرز' : 'Motors'}
          </Link>
          <Link
            className={styles.navLink}
            href={context.href('/property')}
            aria-current={pathname === '/property' ? 'page' : undefined}
          >
            {isUrdu ? 'پراپرٹی' : 'Property'}
          </Link>
        </nav>
        <div className={styles.actions}>
          {session ? (
            <AccountMenu user={session} />
          ) : (
            <Link className={styles.accountLink} href="/login">
              <UserRound aria-hidden="true" />
              <span>{tc('logIn')}</span>
            </Link>
          )}
          <Link href="/dashboard/listings/new" className={styles.postButton}>
            <Plus aria-hidden="true" />
            {t('postAnAd')}
          </Link>
        </div>
      </div>
      <div className={styles.searchRow}>
        <div className={styles.searchInner}>
          <Suspense fallback={<HeaderSearchFallback />}>
            <HeaderSearch />
          </Suspense>
          <nav
            className={styles.shortcuts}
            aria-label={isUrdu ? 'اکاؤنٹ شارٹ کٹس' : 'Member shortcuts'}
          >
            <Link
              href="/messages"
              className={styles.shortcut}
              aria-current={pathname.startsWith('/messages') ? 'page' : undefined}
            >
              <span className={styles.shortcutIcon}>
                <MessageCircle aria-hidden="true" />
                {unreadMessages && (
                  <span
                    className={styles.unreadDot}
                    aria-label={isUrdu ? 'نئے پیغامات' : 'Unread messages'}
                  />
                )}
              </span>
              <span>{t('messages')}</span>
            </Link>
            <Link
              href="/favourites"
              className={styles.shortcut}
              aria-current={pathname === '/favourites' ? 'page' : undefined}
            >
              <Heart aria-hidden="true" />
              <span>{t('favourites')}</span>
            </Link>
            {session ? (
              <NotificationBell variant="header" label={notificationsLabel} />
            ) : (
              <Link
                href="/login"
                className={styles.shortcut}
                aria-label={isUrdu ? 'اطلاعات کے لیے لاگ ان کریں' : 'Log in to view notifications'}
              >
                <Bell aria-hidden="true" />
                <span>{notificationsLabel}</span>
              </Link>
            )}
          </nav>
        </div>
      </div>
    </header>
  );
}
