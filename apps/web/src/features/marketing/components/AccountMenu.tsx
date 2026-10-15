/** Reusable UI rendering and interaction component: AccountMenu. */
'use client';
import { useEffect, useRef, useState } from 'react';
import { useLocale } from 'next-intl';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, UserRound } from 'lucide-react';
import { LogoutButton } from '@/features/auth';
import { ProfileAvatar } from '@/features/profile';
import { profileRequest } from '@/features/profile';
import type { Profile } from '@/features/profile';
import type { SessionUser } from '@/lib/auth/use-session';

export function AccountMenu({ user }: { user: SessionUser }) {
  const ur = useLocale() === 'ur';
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const { data: profile } = useQuery<Profile>({
    queryKey: ['profile', 'me', user.id],
    queryFn: () => profileRequest<Profile>('/me/profile'),
    enabled: open,
    staleTime: 60000,
  });
  useEffect(() => {
    if (!open) return;
    const outside = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', key);
    };
  }, [open]);
  const links = [
    ['/dashboard', 'My profile', 'میری پروفائل'],
    ['/dashboard/listings', 'My ads', 'میرے اشتہارات'],
    ['/messages', 'Messages', 'پیغامات'],
    ['/favourites', 'Favourites', 'پسندیدہ'],
    ['/favourites?tab=searches', 'Saved searches', 'محفوظ تلاشیں'],
    ['/favourites?tab=sellers', 'Following', 'فالو کیے گئے'],
    ['/dashboard/settings', 'Account settings', 'اکاؤنٹ کی ترتیبات'],
  ];
  return (
    <div
      ref={root}
      className="relative"
      onBlur={(e) => {
        if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) setOpen(false);
      }}
    >
      <button
        type="button"
        ref={trigger}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-11 items-center gap-2 rounded-lg text-sm"
      >
        {profile ? (
          <ProfileAvatar src={profile.photoUrl} name={profile.displayName} size={30} />
        ) : (
          <UserRound className="h-6 w-6" aria-hidden="true" />
        )}
        <span>{ur ? 'میرا اکاؤنٹ' : 'My account'}</span>
        <ChevronDown className="h-3 w-3" />
      </button>
      {open && (
        <div className="absolute end-0 top-full z-[70] mt-3 w-64 max-w-[85vw] rounded-2xl border border-border bg-card p-3 text-card-foreground shadow-xl">
          <p className="truncate border-b border-border px-2 pb-3 text-sm font-semibold">
            {profile?.displayName || user.fullName}
          </p>
          <nav aria-label={ur ? 'اکاؤنٹ' : 'Your account'} className="py-2">
            {[
              ...(profile?.profileUrl
                ? [[profile.profileUrl, 'Public profile', 'عوامی پروفائل']]
                : []),
              ...links,
            ].map(([href, en, urdu]) => (
              <Link
                key={href}
                href={href!}
                onClick={() => setOpen(false)}
                className="block rounded-lg px-3 py-2 text-sm hover:bg-muted"
              >
                {ur ? urdu : en}
              </Link>
            ))}
          </nav>
          <div className="border-t border-border pt-2">
            <LogoutButton className="w-full justify-start px-3" />
          </div>
        </div>
      )}
    </div>
  );
}
