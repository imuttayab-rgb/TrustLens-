#!/usr/bin/env sh
# Release-step migration. Run BEFORE new containers start serving, never at
# application boot - two replicas booting together would race on the same
# migration and one would flap its health check.
set -e
echo "==> Applying migrations"
cd /app/database && alembic upgrade head
echo "==> Seeding reference data (idempotent)"
python -m trustlens.db.seed.run reference
echo "==> Release step complete"
