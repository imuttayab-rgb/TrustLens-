const base = require('./index.js');
const reactHooks = require('eslint-plugin-react-hooks');
const jsxA11y = require('eslint-plugin-jsx-a11y');

module.exports = [
  ...base,
  {
    plugins: { 'react-hooks': reactHooks, 'jsx-a11y': jsxA11y },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Accessibility is not optional here: colour-blind buyers misreading a
      // risk badge is a person about to be defrauded.
      ...jsxA11y.configs.recommended.rules,
      'react-hooks/exhaustive-deps': 'error',
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              // Feature-slice boundary: import a feature's public index, never
              // reach into its internals.
              group: ['@/features/*/*', '!@/features/*/index'],
              message: 'Import from the feature index, not its internals.',
            },
            {
              group: ['@/app/*'],
              message: 'Nothing may import from the routing layer.',
            },
          ],
        },
      ],
    },
  },
];
