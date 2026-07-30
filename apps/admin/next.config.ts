import type { NextConfig } from 'next';

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
