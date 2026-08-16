@echo off
REM ============================================================
REM  TrustLens - start everything locally
REM
REM  Double-click this file, or run `start.bat` from a terminal.
REM
REM  Windows batch rather than `make dev`, because the Makefile
REM  sets SHELL := /bin/bash and only runs from Git Bash. This
REM  runs from a plain double-click.
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo  ============================================
echo   TrustLens - starting local environment
echo  ============================================
echo.

REM ---------- 1. Docker ----------
echo [1/6] Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo       Docker is not running. Starting Docker Desktop...
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    echo       Waiting for Docker to be ready. This can take a minute.
    :waitdocker
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if errorlevel 1 goto waitdocker
)
echo       Docker OK.

REM ---------- 2. Infrastructure ----------
echo [2/6] Starting Postgres, Redis, MinIO, Mailpit...
docker compose -f docker/compose/docker-compose.dev.yml up -d
if errorlevel 1 (
    echo.
    echo  !! Could not start the containers. Is Docker Desktop healthy?
    pause
    exit /b 1
)

REM Postgres accepts TCP connections before it is ready to answer
REM queries, so migrations fail if we move on too early.
echo       Waiting for Postgres to accept queries...
:waitpg
timeout /t 3 /nobreak >nul
docker exec trustlens-postgres pg_isready -U trustlens >nul 2>&1
if errorlevel 1 goto waitpg
echo       Infrastructure OK.

REM ---------- 3. Migrations ----------
echo [3/6] Applying database migrations...
pushd database
call uv run alembic upgrade head
popd
if errorlevel 1 (
    echo.
    echo  !! Migrations failed.
    echo     Most likely .env is missing or still has CHANGEME values.
    echo     Run: bash scripts/generate-keys.sh
    pause
    exit /b 1
)

REM ---------- 4. Seed ----------
REM Both seeds are idempotent, so re-running start.bat is safe.
echo [4/6] Seeding reference data and demo sellers...
call uv run python -m trustlens.db.seed.run reference
call uv run python -m trustlens.db.seed.run demo

REM ---------- 5. Backend ----------
REM Separate windows, so you can read each service's logs and close
REM one without killing the others.
echo [5/6] Starting API and worker...
start "TrustLens API" /D "%~dp0" cmd /k uv run uvicorn trustlens_api.main:app --reload --host 127.0.0.1 --port 8000
start "TrustLens Worker" /D "%~dp0" cmd /k uv run python -m trustlens_worker.supervisor

REM ---------- 6. Frontend ----------
echo [6/6] Starting web and admin...
start "TrustLens Web" /D "%~dp0" cmd /k pnpm --filter @trustlens/web dev
start "TrustLens Admin" /D "%~dp0" cmd /k pnpm --filter @trustlens/admin dev

echo.
echo  ============================================
echo   Started. Next.js takes ~30s to compile.
echo  ============================================
echo.
echo   Seller site   http://localhost:3000
echo   Admin panel   http://localhost:3001
echo   API docs      http://localhost:8000/docs
echo   Email inbox   http://localhost:8025
echo   File storage  http://localhost:9001    (minioadmin / minioadmin)
echo.
echo   Demo logins - password is in the second column
echo   ---------------------------------------------
echo   admin@trustlens.dev        Admin^^!Passw0rd123
echo   reviewer@trustlens.dev     Review^^!Passw0rd123
echo   seller.low@trustlens.dev   Seller^^!Passw0rd123
echo   seller.mid@trustlens.dev   Seller^^!Passw0rd123
echo   seller.high@trustlens.dev  Seller^^!Passw0rd123
echo.
echo   Verification emails land in Mailpit (port 8025), not a real
echo   inbox. Open it to click the confirmation link.
echo.
echo   To stop everything: stop.bat
echo.
pause
