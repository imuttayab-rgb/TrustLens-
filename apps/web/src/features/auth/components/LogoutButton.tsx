/** Reusable UI rendering and interaction component: LogoutButton. */
'use client';

import { useLogout } from '@/lib/auth/use-logout';
import { Button } from '@trustlens/ui';
import { LogOut } from 'lucide-react';

export function LogoutButton({ className }: { className?: string }) {
  const logout = useLogout();

  return (
    <Button
      variant="ghost"
      size="sm"
      className={className}
      disabled={logout.isPending}
      onClick={() => logout.mutate()}
    >
      <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
      <span className="hidden sm:inline">{logout.isPending ? 'Signing out…' : 'Log out'}</span>
    </Button>
  );
}
