#!/usr/bin/env bash
# Generate the Ed25519 JWT keypair and the three random secrets for .env.
set -euo pipefail
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
openssl genpkey -algorithm ed25519 -out "$TMP/jwt.pem" 2>/dev/null
openssl pkey -in "$TMP/jwt.pem" -pubout -out "$TMP/jwt.pub" 2>/dev/null
b64() { base64 -w0 "$1" 2>/dev/null || base64 "$1" | tr -d '\n'; }
cat <<OUT
SECURITY_JWT_PRIVATE_KEY=$(b64 "$TMP/jwt.pem")
SECURITY_JWT_PUBLIC_KEY=$(b64 "$TMP/jwt.pub")
SECURITY_OTP_PEPPER=$(openssl rand -base64 32)
SECURITY_TOKEN_PEPPER=$(openssl rand -base64 32)
SECURITY_ENCRYPTION_KEY=$(openssl rand -base64 32)
REVALIDATE_SECRET=$(openssl rand -hex 24)
OUT
