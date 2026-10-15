/** Normalize navigation after login, accepting only paths inside this app. */
export function safeNext(raw: string | null | undefined): string {
  if (!raw || raw.length > 2000) return '/dashboard';
  try {
    let decoded = raw;
    for (let i = 0; i < 5; i += 1) {
      if (
        !decoded.startsWith('/') ||
        decoded.startsWith('//') ||
        decoded.includes('\\') ||
        [...decoded].some(
          (character) => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127,
        )
      )
        return '/dashboard';
      const next = decodeURIComponent(decoded);
      if (next === decoded) break;
      decoded = next;
      if (i === 4) return '/dashboard';
    }
    const base = 'https://trustlens.invalid';
    const url = new URL(raw, base);
    return url.origin === base ? url.pathname + url.search + url.hash : '/dashboard';
  } catch {
    return '/dashboard';
  }
}
