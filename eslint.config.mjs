import js from '@eslint/js';

/**
 * Root flat config.
 *
 * `apps/web` and `apps/admin` carry their own configs for when ESLint runs
 * inside those workspaces. This one exists because the pre-commit hook runs
 * ESLint from the repository root, where tooling files like
 * `configs/lint-staged.config.js` and `scripts/**` would otherwise have no
 * config at all - which is a hard error in ESLint v9, not a skip.
 *
 * Deliberately not type-checked: these are CommonJS tooling files with no
 * tsconfig, so `recommendedTypeChecked` cannot apply to them. The handful of
 * Node globals are declared inline rather than pulling in `globals`, which is
 * not hoisted to the workspace root under pnpm.
 */
const nodeGlobals = {
  module: 'writable',
  require: 'readonly',
  exports: 'writable',
  process: 'readonly',
  console: 'readonly',
  __dirname: 'readonly',
  __filename: 'readonly',
  Buffer: 'readonly',
  URL: 'readonly',
};

export default [
  {
    ignores: [
      '**/node_modules/**',
      '**/dist/**',
      '**/.next/**',
      '**/.turbo/**',
      '**/*.gen.ts',
      '.venv/**',
      'apps/web/**',
      'apps/admin/**',
    ],
  },
  {
    files: ['**/*.{js,cjs}'],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'commonjs',
      globals: nodeGlobals,
    },
    rules: {
      ...js.configs.recommended.rules,
      'no-console': 'off', // tooling scripts legitimately print
    },
  },
  {
    files: ['**/*.mjs'],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: nodeGlobals,
    },
    rules: {
      ...js.configs.recommended.rules,
      'no-console': 'off',
    },
  },
];
