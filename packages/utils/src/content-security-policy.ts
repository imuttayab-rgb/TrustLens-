/** Browser document policy shared by web/admin. No secrets enter this module. */
export function documentPolicy(
  nonce: string,
  options: { development: boolean; origins: string[]; local: boolean },
): string {
  const origins = options.origins.flatMap((raw) => {
    try {
      const url = new URL(raw);
      return ['http:', 'https:', 'ws:', 'wss:'].includes(url.protocol) &&
        !url.username &&
        !url.password
        ? [url.origin]
        : [];
    } catch {
      return [];
    }
  });
  // Loopback allowances are for the Docker localhost profile only.
  const local = options.local
    ? 'http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*'
    : '';
  const connections = [...new Set(origins)].join(' ');
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' 'wasm-unsafe-eval'${options.development ? " 'unsafe-eval'" : ''}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' https: data: blob: " + local + ' ' + connections,
    "font-src 'self' data:",
    "connect-src 'self' " + connections + ' ' + local,
    "media-src 'self' blob: " + connections + ' ' + local,
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ');
}
