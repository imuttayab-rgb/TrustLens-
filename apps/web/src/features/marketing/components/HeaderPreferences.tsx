/** Reusable UI rendering and interaction component: HeaderPreferences. */
'use client';

import { LocaleSwitcher } from '@/i18n/LocaleSwitcher';
import { THEME_COOKIE, type Theme } from '@trustlens/ui';
import { Moon, Sun } from 'lucide-react';
import { useLocale } from 'next-intl';
import { useEffect, useState } from 'react';
import styles from './BrowseNav.module.css';

export function HeaderPreferences() {
  const isUrdu = useLocale() === 'ur';
  const [theme, setTheme] = useState<Theme | null>(null);
  useEffect(() => {
    const html = document.documentElement;
    const sync = () => setTheme(html.classList.contains('dark') ? 'dark' : 'light');
    sync();
    // Keep this selector in sync if another existing theme control is used.
    const observer = new MutationObserver(sync);
    observer.observe(html, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  function apply(next: Theme) {
    document.documentElement.classList.toggle('dark', next === 'dark');
    document.cookie = `${THEME_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
    setTheme(next);
  }
  return (
    <div className={styles.preferences} data-header-preferences="visible">
      <LocaleSwitcher className={styles.locale ?? ''} />
      <div
        role="group"
        aria-label={isUrdu ? 'رنگوں کا انداز' : 'Colour theme'}
        className={styles.theme}
      >
        <button
          type="button"
          disabled={theme === null}
          aria-pressed={theme === 'light'}
          onClick={() => apply('light')}
        >
          <Sun aria-hidden="true" />
          <span>{isUrdu ? 'لائٹ' : 'Light'}</span>
        </button>
        <button
          type="button"
          disabled={theme === null}
          aria-pressed={theme === 'dark'}
          onClick={() => apply('dark')}
        >
          <Moon aria-hidden="true" />
          <span>{isUrdu ? 'ڈارک' : 'Dark'}</span>
        </button>
      </div>
    </div>
  );
}
