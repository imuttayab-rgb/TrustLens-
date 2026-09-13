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

REM Wait for BOTH Postgres and Redis, not just Postgres.
REM
REM Postgres accepts TCP connections before it can answer queries, so
REM migrations fail if we move on too early. Redis matters just as much: the
REM API and worker both connect to it at startup, and if they win the race
REM they print a wall of "connection error ... retries remaining" that looks
REM like a broken install. They do recover, but nobody believes that while
REM reading red text.
echo       Waiting for Postgres...
:waitpg
timeout /t 3 /nobreak >nul
docker exec trustlens-postgres pg_isready -U trustlens >nul 2>&1
if errorlevel 1 goto waitpg

REM Redis is checked FROM THE HOST, over a real PING/PONG round trip.
REM
REM `docker exec redis-cli ping` is the obvious check and it is the wrong one:
REM it asks the container whether it is ready, while the API and worker connect
REM from outside through Docker Desktop's port-forwarding proxy. That proxy
REM accepts a TCP connection and then resets it while it is still wiring up,
REM which surfaces as Windows error 64, "The specified network name is no
REM longer available" - a confusing message that has nothing to do with names
REM or networks being unavailable.
REM
REM So this connects the same way the app does and insists on reading +PONG
REM back. Anything less passes too early.
echo       Waiting for Redis (from the host)...
:waitredis
timeout /t 2 /nobreak >nul
powershell -NoProfile -Command ^
  "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',6379); $s = $c.GetStream(); $b = [Text.Encoding]::ASCII.GetBytes(\"PING`r`n\"); $s.Write($b,0,$b.Length); $s.ReadTimeout = 2000; $r = New-Object byte[] 16; $n = $s.Read($r,0,16); $c.Close(); if ([Text.Encoding]::ASCII.GetString($r,0,$n) -like '*PONG*') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 goto waitredis

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

REM ---------- 4b. Ports ----------
REM A service that cannot bind its port does not crash loudly - uvicorn logs
REM an error into a window nobody reads, and the symptom the user sees is
REM "login is broken". Cheaper to refuse to start and say why.
echo [4b/6] Checking ports are free...
set PORTS_BUSY=
for %%P in (3000 3001 8000) do (
    powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %%P -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }" >nul 2>&1
    if errorlevel 1 (
        echo       Port %%P is already in use.
        set PORTS_BUSY=1
    )
)
if defined PORTS_BUSY (
    echo.
    echo  !! Something is already using a port TrustLens needs.
    echo     Usually a previous run that was closed with the X button
    echo     rather than stop.bat.
    echo.
    echo     Run stop.bat first, then start.bat again.
    echo.
    pause
    exit /b 1
)
echo       Ports OK.

REM ---------- 5. Backend ----------
REM Separate windows, so you can read each service's logs and close
REM one without killing the others.
echo [5/6] Starting API and worker...
start "TrustLens API" /D "%~dp0" cmd /k uv run uvicorn trustlens_api.main:app --host 127.0.0.1 --port 8000
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
echo   Browse        http://localhost:3000/browse
echo   Admin panel   http://localhost:3001
echo   API docs      http://localhost:8000/docs
echo   Email inbox   http://localhost:8025
echo   File storage  http://localhost:9001    (minioadmin / minioadmin)
echo.
echo   Demo logins - password is in the second column
echo   ---------------------------------------------
echo   admin@trustlens.dev        Admin!Passw0rd123
echo   reviewer@trustlens.dev     Review!Passw0rd123
echo   seller.low@trustlens.dev   Seller!Passw0rd123
echo   seller.mid@trustlens.dev   Seller!Passw0rd123
echo   seller.high@trustlens.dev  Seller!Passw0rd123
echo.
echo   Verification emails land in Mailpit (port 8025), not a real
echo   inbox. Open it to click the confirmation link.
echo.
echo   To stop everything: stop.bat
echo.
pause
