module.exports = {
  '*.{ts,tsx,js,jsx}': [
    'prettier --config configs/prettier.config.js --write',
    'eslint --fix --max-warnings=0',
  ],
  '*.py': ['ruff check --fix', 'ruff format'],
  '*.{json,yml,yaml,md}': ['prettier --config configs/prettier.config.js --write'],
};
