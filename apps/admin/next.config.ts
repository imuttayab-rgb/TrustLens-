import { config as loadEnv } from 'dotenv';
import type { NextConfig } from 'next';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

// Next only reads .env files from its own project directory, so in this
// monorepo `apps/admin` never sees the root .env. Real environment variables
// (Vercel, CI) still win.
loadEnv({ path: resolve(dirname(fileURLToPath(import.meta.url)), '../../.env'), override: false });

const config: NextConfig = {
  reactStrictMode: true,
  // Self-contained server bundle: `.next/standalone` carries its own minimal
  // node_modules, so the runtime image needs no pnpm install and no workspace.
  //
  // Required for `docker/web.Dockerfile` to build at all - it copies
  // `.next/standalone`, which Next does not emit without this line. Vercel
  // ignores it and builds natively, so nothing is lost by keeping it on.
  output: 'standalone',
  // The workspace root, so Next traces files from the monorepo rather than
  // from apps/<name> and silently omits the shared packages.
  outputFileTracingRoot: resolve(dirname(fileURLToPath(import.meta.url)), '../..'),
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
