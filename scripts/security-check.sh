#!/usr/bin/env bash
# Automated security checks against a running stack (P10-03).
#
#   bash scripts/security-check.sh
#
# Not a penetration test. These are the checks that catch the mistakes this
# codebase could actually make, run automatically so they are re-run after
# every change instead of once before a demo.
#
# The PII scan matters most. This system holds CNIC numbers, phone numbers and
# selfies; the public API is PII-free by construction (its schema has no such
# field), and this verifies that construction still holds at the wire.
set -uo pipefail

API=${API_BASE_URL:-http://localhost:8000}
WEB=${WEB_BASE_URL:-http://localhost:3000}

pass=0
fail=0
warn=0

ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; pass=$((pass + 1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=$((fail + 1)); }
note() { printf '  \033[33mWARN\033[0m  %s\n' "$1"; warn=$((warn + 1)); }

echo ""
echo "==> Security checks against $API"
echo ""

# ── 1. Authentication is required where it should be ─────────────────
echo "  Authentication"
for path in \
  "/api/v1/me" \
  "/api/v1/listings" \
  "/api/v1/admin/review-cases" \
  "/public/v1/sellers/x/trust-score"
do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$API$path")
  case "$code" in
    401|403) ok "$path refuses anonymous access ($code)" ;;
    404)     note "$path returned 404 - route may have moved" ;;
    *)       bad "$path returned $code to an anonymous caller" ;;
  esac
done

# ── 2. No PII on the public surfaces ─────────────────────────────────
echo ""
echo "  PII exposure"
BODY=$(curl -s --max-time 15 "$API/api/v1/public/sellers/ayesha-traders/trust-score" 2>/dev/null)
PUBLIC_STATUS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$API/api/v1/public/sellers/ayesha-traders/trust-score")
if [ -z "$BODY" ] || [ "$PUBLIC_STATUS" != "200" ]; then
  note "public score PII check NOT RUN: a valid synthetic seller response is required (HTTP $PUBLIC_STATUS)"
else
  leaked=0
  # CNIC: 5 digits - 7 digits - 1
  echo "$BODY" | grep -Eq '[0-9]{5}-[0-9]{7}-[0-9]' && { bad "CNIC pattern in the public payload"; leaked=1; }
  echo "$BODY" | grep -Eq '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' && { bad "email address in the public payload"; leaked=1; }
  echo "$BODY" | grep -Eq '\+92[0-9]{10}|03[0-9]{9}' && { bad "phone number in the public payload"; leaked=1; }
  echo "$BODY" | grep -Eiq '"(passwordHash|password|cnic|nationalId|selfieUrl|documentUrl)"' && { bad "a forbidden field name in the public payload"; leaked=1; }
  [ "$leaked" -eq 0 ] && ok "no CNIC, email, phone or document URL in the public score"
fi

# ── 3. Errors do not leak internals ──────────────────────────────────
echo ""
echo "  Error handling"
ERR=$(curl -s --max-time 10 "$API/api/v1/sellers/not-a-uuid/trust-score")
if echo "$ERR" | grep -qiE 'traceback|sqlalchemy|psycopg|File "/|line [0-9]+, in'; then
  bad "a stack trace or driver name is visible in an error response"
else
  ok "errors carry no stack trace or driver internals"
fi
if echo "$ERR" | grep -q '"requestId"'; then
  ok "errors carry a requestId for support"
else
  note "error response has no requestId"
fi

# ── 4. Security headers ──────────────────────────────────────────────
echo ""
echo "  HTTP headers"
HEADERS=$(curl -s -D - -o /dev/null --max-time 10 "$WEB/" 2>/dev/null)
check_header() {
  if echo "$HEADERS" | grep -qi "^$1:"; then ok "$1 is set"; else bad "$1 is missing"; fi
}
check_header "x-content-type-options"
check_header "x-frame-options"
check_header "referrer-policy"
check_header "content-security-policy"
case "$WEB" in https://*) check_header "strict-transport-security" ;; esac

API_HEADERS=$(curl -s -D - -o /dev/null --max-time 10 "$API/health/live" 2>/dev/null)
if echo "$API_HEADERS" | grep -qi '^server: uvicorn'; then
  bad "the API advertises its server software (Server: uvicorn)"
else
  ok "the API does not advertise its server software"
fi
if echo "$HEADERS" | grep -qi '^x-powered-by:'; then
  bad "X-Powered-By is exposed"
else
  ok "X-Powered-By is not exposed"
fi

# ── 5. Login brute force is throttled ────────────────────────────────
echo ""
echo "  Brute force"
throttled=0
for _ in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
    -X POST "$API/api/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -d '{"email":"nobody@trustlens.dev","password":"WrongPassword!123"}')
  [ "$code" = "429" ] && { throttled=1; break; }
done
if [ "$throttled" -eq 1 ]; then
  ok "repeated failed logins are rate limited (429)"
else
  bad "40 failed logins from one IP were not throttled - password spraying is unimpeded"
fi

# ── 6. Docs are closed in production ─────────────────────────────────
echo ""
echo "  Production posture"
# Health deliberately exposes no environment/version details. Operator declares
# the expected posture; never infer success from a missing field.
ENVIRON=${TRUSTLENS_CHECK_ENV:-staging}
DOCS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$API/docs")
if [ "$ENVIRON" = "production" ] && [ "$DOCS" = "200" ]; then
  bad "Swagger is open at /docs while production posture is expected"
elif [ "$ENVIRON" = "production" ]; then
  ok "internal API docs are closed in production"
else
  note "production-only docs closure NOT RUN (expected posture: $ENVIRON)"
fi

# ── 7. Secrets are not in the image or the repo ──────────────────────
echo ""
echo "  Secrets"
if git -C "$(dirname "$0")/.." ls-files --error-unmatch .env.production >/dev/null 2>&1; then
  bad ".env.production is TRACKED IN GIT - rotate every secret in it now"
else
  ok ".env.production is not tracked by git"
fi
if grep -q '^\.env\.\*' "$(dirname "$0")/../.dockerignore" 2>/dev/null; then
  ok ".env files are excluded from the Docker build context"
else
  bad ".env files are NOT excluded from the Docker build context - secrets could be baked into a layer"
fi

echo ""
echo "  ------------------------------------------------------------"
printf '  %s passed, %s failed, %s warnings\n' "$pass" "$fail" "$warn"
echo ""
[ "$fail" -eq 0 ] || exit 1
