/** Public browser configuration. Never add API keys or private service URLs here.
 * NEXT_PUBLIC values are baked into Next.js output and require a rebuild after changes.
 */
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
).replace(/\/$/, '');
