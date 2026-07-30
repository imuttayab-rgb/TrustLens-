const js = require('@eslint/js');
const ts = require('typescript-eslint');
const prettier = require('eslint-config-prettier');

/**
 * Base flat config. The rules below are not stylistic - each one prevents a
 * class of bug we specifically care about in this codebase.
 */
module.exports = [
  js.configs.recommended,
  ...ts.configs.recommendedTypeChecked,
  prettier,
  {
    languageOptions: { parserOptions: { projectService: true } },
    rules: {
      // `unknown` + narrowing instead. `any` silently disables every other
      // guarantee in this list.
      '@typescript-eslint/no-explicit-any': 'error',
      // An unawaited promise swallows its rejection - in an API client that
      // means a failed request that looks like a success.
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': 'error',
      '@typescript-eslint/consistent-type-imports': ['error', { prefer: 'type-imports' }],
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
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
  { ignores: ['dist/**', '.next/**', 'node_modules/**', '**/*.gen.ts'] },
];
