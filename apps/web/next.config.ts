import { config as loadEnv } from 'dotenv';
import type { NextConfig } from 'next';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

// Next only reads .env files from its own project directory, so in this
// monorepo `apps/web` never sees the root .env and API_BASE_URL_INTERNAL comes
// back undefined - server-rendered pages then fetch "undefined/public/v1/..."
// and 500. Real environment variables (Vercel, CI) still win.
loadEnv({ path: resolve(dirname(fileURLToPath(import.meta.url)), '../../.env'), override: false });

const config: NextConfig = {
  reactStrictMode: true,
  // Workspace packages ship as source so Tailwind can tree-shake them and the
  // app can override; Next must therefore transpile them.
  transpilePackages: [
    '@trustlens/ui',
    '@trustlens/constants',
    '@trustlens/utils',
    '@trustlens/validation',
    '@trustlens/api-client',
  ],
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          // camera=(self) is required for the selfie capture step.
          {
            key: 'Permissions-Policy',
            value: 'camera=(self), microphone=(), geolocation=(), payment=()',
          },
        ],
      },
    ];
  },
};

export default config;
