'use client';
/** User-controlled browser push subscription button. */
import { Bell } from 'lucide-react';
import { useVoiceCalls } from '../calls/context';
export function CallNotifications() {
  const calls = useVoiceCalls();
  if (!calls.pushAvailable) return null;
  return (
    <button
      type="button"
      onClick={() => void calls.toggleNotifications()}
      className="flex items-center gap-1 rounded border border-border px-2 py-1"
      aria-pressed={calls.notifications}
    >
      <Bell size={14} />
      {calls.notifications ? 'Call alerts on' : 'Enable call alerts'}
    </button>
  );
}
