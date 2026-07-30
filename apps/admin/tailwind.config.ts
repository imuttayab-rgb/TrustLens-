import preset from '@trustlens/config-tailwind/preset';
import type { Config } from 'tailwindcss';

export default {
  presets: [preset],
  content: [
    './src/**/*.{ts,tsx}',
    // Scan the design system too, or its class names get purged.
    '../../packages/ui/src/**/*.{ts,tsx}',
  ],
} satisfies Config;
