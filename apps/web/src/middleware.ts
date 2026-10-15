/** Create a fresh document nonce; Next reads the request CSP during rendering. */
import { NextResponse, type NextRequest } from 'next/server';
import { documentPolicy } from '@trustlens/utils';

export function middleware(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const appUrl = process.env.CSP_APP_ORIGIN ?? 'http://localhost:3000';
  const local = ['localhost', '127.0.0.1'].includes(new URL(appUrl).hostname);
  const policy = documentPolicy(nonce, {
    development: process.env.NODE_ENV === 'development',
    local,
    origins: [
      process.env.CSP_API_ORIGIN ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? '',
      process.env.CSP_MEDIA_ORIGIN ?? '',
      ...(process.env.CSP_CONNECT_ORIGINS ?? '').split(/[,\s]+/),
    ],
  });
  const headers = new Headers(request.headers);
  headers.set('x-nonce', nonce);
  headers.set('Content-Security-Policy', policy);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set('Content-Security-Policy', policy);
  // HTML bearing a nonce must not be shared between visitors or cached at a CDN.
  response.headers.set('Cache-Control', 'private, no-store');
  if (!local && appUrl.startsWith('https://')) {
    response.headers.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  }
  return response;
}
export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|sw.js|manifest.webmanifest).*)'],
};
