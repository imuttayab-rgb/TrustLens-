import js from '@eslint/js';
import tseslint from 'typescript-eslint';

/**
 * Root flat config.
 *
 * Covers two groups that would otherwise have no config at all, which in
 * ESLint v9 is a hard error rather than a skip:
 *
 * - repo tooling (`configs/**`, `scripts/**`), linted by the pre-commit hook,
 *   which runs from the repository root;
 * - the shared `packages/*` libraries, whose `lint` script is `eslint src`
 *   but which ship no config of their own.
 *
 * `apps/web` and `apps/admin` are excluded because they carry their own
 * Next-aware configs.
 *
 * The TypeScript rules here are deliberately the non-type-checked set. The
 * type-aware ones in `@trustlens/config-eslint` need a `projectService` and a
 * tsconfig per package; `pnpm typecheck` already runs the full compiler over
 * every package, so this layer would duplicate that work for no new findings.
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

  // ── Repo tooling (CommonJS) ────────────────────────────────────────
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
    rules: { ...js.configs.recommended.rules, 'no-console': 'off' },
  },

  // ── Shared packages (TypeScript) ───────────────────────────────────
  ...tseslint.configs.recommended.map((config) => ({
    ...config,
    files: ['packages/**/*.{ts,tsx}', 'testing/**/*.{ts,tsx}'],
  })),
  {
    files: ['packages/**/*.{ts,tsx}', 'testing/**/*.{ts,tsx}'],
    rules: {
      // `unknown` plus narrowing instead: `any` silently disables every other
      // guarantee in the list.
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      eqeqeq: ['error', 'always', { null: 'ignore' }],
      'prefer-const': 'error',
      'no-restricted-globals': [
        'error',
        // Tokens must never touch storage that JavaScript can read (ADR-0006).
        { name: 'localStorage', message: 'Never store tokens or PII in localStorage.' },
        { name: 'sessionStorage', message: 'Never store tokens or PII in sessionStorage.' },
      ],
    },
  },
];
