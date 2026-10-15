/** Next.js route/layout composition for manifest.ts: manifest. */
import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: '/', name: 'TrustLens', short_name: 'TrustLens', start_url: '/messages', scope: '/',
    display: 'standalone', background_color: '#ffffff', theme_color: '#0f766e',
    icons: [{ src: '/call-icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
  };
}
