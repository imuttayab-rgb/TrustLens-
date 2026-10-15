/** Private browser history: bounded IDs only, no names, locations or signed URLs. */
export const HISTORY_KEY = 'trustlens:recently-viewed';
export const HISTORY_EVENT = 'trustlens:history-changed';
const TTL = 30 * 24 * 60 * 60 * 1000;
const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export interface HistoryEntry {
  id: string;
  viewedAt: number;
}

export function readHistory(now = Date.now()): HistoryEntry[] {
  try {
    const raw: unknown = JSON.parse(window.localStorage.getItem(HISTORY_KEY) ?? '[]');
    const values = Array.isArray(raw) ? raw : [];
    const seen = new Set<string>();
    const clean = values
      .flatMap((item: unknown) => {
        if (!item || typeof item !== 'object') return [];
        const value = item as Record<string, unknown>;
        if (typeof value.id !== 'string' || !ID.test(value.id) || seen.has(value.id)) return [];
        const viewedAt = typeof value.viewedAt === 'number' ? value.viewedAt : now;
        if (!Number.isFinite(viewedAt) || viewedAt > now || now - viewedAt > TTL) return [];
        seen.add(value.id);
        return [{ id: value.id, viewedAt }];
      })
      .slice(0, 12);
    // Also removes fields from the old full-listing format on the first read.
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(clean));
    return clean;
  } catch {
    return [];
  } // Optional convenience feature when browser storage is unavailable.
}
export function recordHistory(id: string): void {
  if (!ID.test(id)) return;
  try {
    const entries = [
      { id, viewedAt: Date.now() },
      ...readHistory().filter((v) => v.id !== id),
    ].slice(0, 12);
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(entries));
    window.dispatchEvent(new Event(HISTORY_EVENT));
  } catch {
    /* Disabled/full storage must not prevent viewing the listing. */
  }
}
export function clearRecentlyViewed(): void {
  try {
    window.localStorage.removeItem(HISTORY_KEY);
  } catch {
    /* Storage may be disabled. */
  }
  window.dispatchEvent(new Event(HISTORY_EVENT));
}
