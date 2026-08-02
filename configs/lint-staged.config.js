// `ruff` lives in the uv virtualenv, not on PATH, so a bare `ruff` breaks the
// pre-commit hook on any machine where the venv is not activated - which is
// every fresh clone. `uv run` resolves it from the project environment.
//
// Lockfiles are excluded: they are generated, enormous, and reformatting them
// makes the hook slow enough that people start passing --no-verify.
module.exports = {
  '*.{ts,tsx,js,jsx}': [
    'prettier --config configs/prettier.config.js --write',
    'eslint --fix --max-warnings=0',
  ],
  '*.py': ['uv run ruff check --fix', 'uv run ruff format'],
  '*.{json,yml,yaml,md}': ['prettier --config configs/prettier.config.js --write'],
};
