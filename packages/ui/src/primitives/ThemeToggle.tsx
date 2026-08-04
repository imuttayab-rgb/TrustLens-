'use client';

import { Moon, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';
import { cn } from '../lib/cn';
import { DEFAULT_THEME, THEME_COOKIE, type Theme } from '../lib/theme';

/**
 * Light/dark switch.
 *
 * The preference lives in a cookie rather than localStorage for two reasons.
 * The server can read a cookie, so the correct class is on `<html>` in the
 * very first response and there is no flash of the wrong theme — the usual
 * failure of a localStorage-based toggle, which cannot run until after paint.
 * And the lint config bans localStorage outright to keep tokens out of
 * JS-readable storage; carving an exception for a theme would blunt a rule
 * that is worth keeping absolute.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>(DEFAULT_THEME);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setTheme(document.documentElement.classList.contains('dark') ? 'dark' : 'light');
    setMounted(true);
  }, []);

  function apply(next: Theme) {
    document.documentElement.classList.toggle('dark', next === 'dark');
    // A year, so the choice survives; Lax because nothing here is sensitive
    // and a cross-site request has no business changing someone's theme.
    document.cookie = `${THEME_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
    setTheme(next);
  }

  const next: Theme = theme === 'dark' ? 'light' : 'dark';

  return (
    <button
      type="button"
      onClick={() => apply(next)}
      // Until mounted we cannot know which theme the server chose, so the
      // label would be a guess. Hiding it from assistive tech for one frame
      // is better than announcing the wrong action.
      aria-hidden={!mounted}
      tabIndex={mounted ? 0 : -1}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className={cn(
        'text-muted-foreground hover:text-foreground hover:bg-muted/60 focus-visible:ring-ring',
        'relative grid h-9 w-9 place-items-center rounded-md transition-colors',
        'focus-visible:ring-2 focus-visible:outline-none',
        className,
      )}
    >
      {/* Both icons render and cross-fade, so the button never reflows and
          there is nothing to lay out on first paint. */}
      <Sun
        className={cn(
          'absolute h-4 w-4 transition-all duration-300',
          theme === 'dark' ? 'scale-100 rotate-0 opacity-100' : 'scale-75 -rotate-90 opacity-0',
        )}
        aria-hidden="true"
      />
      <Moon
        className={cn(
          'absolute h-4 w-4 transition-all duration-300',
          theme === 'dark' ? 'scale-75 rotate-90 opacity-0' : 'scale-100 rotate-0 opacity-100',
        )}
        aria-hidden="true"
      />
    </button>
  );
}
