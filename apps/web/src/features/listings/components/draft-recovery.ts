/** Reusable UI rendering and interaction component: draft recovery. */
'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Editor, SpecForm } from './spec-editor';
import {
  readDraftRecovery,
  writeDraftRecovery,
  removeDraftRecovery,
} from '../../../lib/draft-recovery-cache';
import { categoryNode } from '@trustlens/constants';

export type Recovery<T extends SpecForm> = {
  version: 1;
  at: number;
  editor: Editor<T>;
  categories: [string, Editor<T>][];
  dirty: boolean;
};
const TTL = 24 * 60 * 60 * 1000;
export function readRecovery<T extends SpecForm>(
  raw: string | null,
  now = Date.now(),
): Recovery<T> | null {
  if (!raw || raw.length > 400000) return null;
  try {
    const r = JSON.parse(raw) as Recovery<T>;
    const object = (x: unknown): x is Record<string, unknown> =>
      !!x && typeof x === 'object' && !Array.isArray(x);
    const text = (x: unknown, max: number) => typeof x === 'string' && x.length <= max;
    const specs = (x: unknown) =>
      Array.isArray(x) &&
      x.length <= 20 &&
      x.every((s) => object(s) && text(s.key, 80) && text(s.value, 160));
    const content = (x: unknown) => object(x) && text(x.description, 8000) && specs(x.specs);
    const details = (x: unknown) =>
      object(x) &&
      content(x) &&
      text(x.title, 160) &&
      text(x.category, 80) &&
      (x.categoryNodeId == null ||
        (typeof x.categoryNodeId === 'string' &&
          categoryNode(x.categoryNodeId)?.selectable === true)) &&
      ['condition', 'price'].every((k) => x[k] === undefined || text(x[k], 80)) &&
      Object.keys(x).every((k) =>
        [
          'title',
          'description',
          'category',
          'categoryNodeId',
          'condition',
          'price',
          'specs',
          'showPhone',
          'negotiable',
        ].includes(k),
      ) &&
      (x.showPhone === undefined || typeof x.showPhone === 'boolean') &&
      (x.negotiable === undefined || typeof x.negotiable === 'boolean');
    const tracking = (x: unknown) =>
      object(x) &&
      object(x.automatic) &&
      Object.keys(x.automatic).length <= 20 &&
      Object.entries(x.automatic).every(([k, v]) => text(k, 80) && text(v, 160)) &&
      Array.isArray(x.suppressed) &&
      x.suppressed.length <= 200 &&
      x.suppressed.every((k) => text(k, 80));
    const valid = (e: unknown) =>
      object(e) &&
      details(e.details) &&
      tracking(e.tracking) &&
      (e.undo === null ||
        (object(e.undo) &&
          object(e.undo.before) &&
          details(e.undo.before.details) &&
          tracking(e.undo.before.tracking) &&
          content(e.undo.after)));
    if (
      !object(r) ||
      r.version !== 1 ||
      !Number.isFinite(r.at) ||
      now - r.at > TTL ||
      r.at > now + 60000 ||
      typeof r.dirty !== 'boolean' ||
      !valid(r.editor) ||
      !Array.isArray(r.categories) ||
      r.categories.length > 20 ||
      !r.categories.every(
        (row) => Array.isArray(row) && row.length === 2 && text(row[0], 240) && valid(row[1]),
      )
    )
      return null;
    return r;
  } catch {
    return null;
  }
}
/** Per-user recovery across in-app navigation. Refresh-safe drafts use the existing Save draft API. No persistent browser storage. */
export function useDraftRecovery<T extends SpecForm>({
  userId,
  listingId,
  hydrated,
  dirty,
  published,
  editor,
  categories,
}: {
  userId?: string | undefined;
  listingId: string | null;
  hydrated: boolean;
  dirty: boolean;
  published: boolean;
  editor: Editor<T>;
  categories: Map<string, Editor<T>>;
}) {
  const key = userId ? `tl-ad-recovery-v1:${userId}:${listingId ?? 'new'}` : null;
  const latestKey = useRef(key);
  latestKey.current = key;
  const suppressedEditor = useRef<Editor<T> | null>(null);
  const signedOut = useRef(false);
  useEffect(() => {
    const clear = () => {
      signedOut.current = true;
    };
    window.addEventListener('tl:logout', clear);
    return () => window.removeEventListener('tl:logout', clear);
  }, []);
  const [checked, setChecked] = useState<string | null>(null);
  const [recovery, setRecovery] = useState<Recovery<T> | null>(null);
  const latest = useRef({
    version: 1 as const,
    at: Date.now(),
    editor,
    categories: [...categories.entries()].slice(-20),
    dirty,
  });
  latest.current = {
    version: 1,
    at: Date.now(),
    editor,
    categories: [...categories.entries()].slice(-20),
    dirty,
  };
  useEffect(() => {
    if (!key || !hydrated) return;
    let cached: Recovery<T> | null = null;
    try {
      cached = readRecovery<T>(readDraftRecovery(key));
    } catch {
      /* A malformed recovery cannot prevent the server Save draft flow. */
    }
    setRecovery(cached && (cached.dirty || cached.categories.length) ? cached : null);
    setChecked(key);
  }, [key, hydrated]);
  useEffect(() => {
    if (!key || checked !== key || !hydrated || recovery) return;
    const write = () => {
      if (
        latestKey.current !== key ||
        signedOut.current ||
        latest.current.editor === suppressedEditor.current
      )
        return;
      try {
        if (published) removeDraftRecovery(key);
        else writeDraftRecovery(key, JSON.stringify(latest.current));
      } catch {
        /* Recovery cannot interrupt the existing server draft flow. */
      }
    };
    const timer = setTimeout(write, 400);
    window.addEventListener('pagehide', write);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('pagehide', write);
      write();
    };
  }, [key, checked, hydrated, recovery, published, editor, dirty]);
  const clear = useCallback(() => {
    suppressedEditor.current = latest.current.editor;
    if (key)
      try {
        removeDraftRecovery(key);
      } catch {
        /* In-memory draft recovery must not interrupt editing. */
      }
    setRecovery(null);
  }, [key]);
  const accept = useCallback(() => setRecovery(null), []);
  return { recovery, clear, accept };
}
