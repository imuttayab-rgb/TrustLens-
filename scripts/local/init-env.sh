#!/usr/bin/env bash
# Generate per-install secrets once. Never rotate existing data-encryption keys.
set -Eeuo pipefail
umask 077
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
if [[ -f .env.production ]]; then
  echo 'Existing .env.production preserved.'
  exit 0
fi
command -v openssl >/dev/null || { echo 'OpenSSL is required (included in Git for Windows).' >&2; exit 1; }
staged_env="$(mktemp .env.production.new.XXXXXX)"
trap 'rm -f "$staged_env"' EXIT
local_db_password="$(openssl rand -hex 24)"
local_storage_password="$(openssl rand -hex 24)"
# Passwords use hex, so they are safe in PostgreSQL URLs and Compose values.
awk -v db="$local_db_password" -v s3="$local_storage_password" '
 /^POSTGRES_PASSWORD=/ {print "POSTGRES_PASSWORD=" db; next}
 /^DATABASE_URL=/ {print "DATABASE_URL=postgresql+asyncpg://trustlens:" db "@postgres:5432/trustlens"; next}
 /^DATABASE_URL_SYNC=/ {print "DATABASE_URL_SYNC=postgresql+psycopg://trustlens:" db "@postgres:5432/trustlens"; next}
 /^STORAGE_SECRET_ACCESS_KEY=/ {print "STORAGE_SECRET_ACCESS_KEY=" s3; next}
 {print}
' .env.production.example > "$staged_env"
bash scripts/generate-keys.sh >> "$staged_env"
chmod 600 "$staged_env"
# Hard-link creation fails if another process created the target in the meantime.
ln "$staged_env" .env.production
printf 'PRIVATE_CONFIG_CREATED; no secrets printed. Keep this file safe.\n'
