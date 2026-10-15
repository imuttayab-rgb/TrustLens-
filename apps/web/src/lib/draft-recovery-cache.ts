/** Unsaved public ad text survives in-app navigation only. Refresh-safe drafts use the API.
 * Never persist this content in browser storage: free text can contain personal details.
 */
const drafts = new Map<string, string>();
export function readDraftRecovery(key: string): string | null {
  return drafts.get(key) ?? null;
}
export function writeDraftRecovery(key: string, value: string): void {
  if (value.length > 400000) return;
  drafts.delete(key);
  drafts.set(key, value);
  while (drafts.size > 5) drafts.delete(drafts.keys().next().value!);
}
export function removeDraftRecovery(key: string): void {
  drafts.delete(key);
}
export function clearDraftRecovery(): void {
  drafts.clear();
}
