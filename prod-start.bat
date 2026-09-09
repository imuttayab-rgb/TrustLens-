@echo off
setlocal enabledelayedexpansion
REM TrustLens - start the full production stack on Windows.
REM
REM Double-click this file. It creates secrets on first run, builds the four
REM images, starts everything, and checks that it actually works.
REM
REM Stop it again with prod-stop.bat.

cd /d "%~dp0"
title TrustLens - production stack

echo.
echo   TrustLens - production stack
echo   ============================
echo.

REM ---- Docker must be running -------------------------------------------
docker info >nul 2>&1
if errorlevel 1 (
  echo   [X] Docker Desktop is not running.
  echo.
  echo       Start Docker Desktop, wait for the whale icon to stop animating,
  echo       then run this file again.
  echo.
  pause
  exit /b 1
)
echo   [OK] Docker is running

REM ---- First run: create .env.production --------------------------------
if not exist ".env.production" (
  echo   [..] First run - creating .env.production with fresh secrets
  copy /y ".env.production.example" ".env.production" >nul
  bash scripts/generate-keys.sh >> ".env.production" 2>nul
  if errorlevel 1 (
    echo   [X] Could not generate secrets. Git Bash is required ^(it ships with Git for Windows^).
    pause
    exit /b 1
  )

  REM Replace the placeholder passwords with random ones. A stack that boots
  REM on a default password is a stack that ships on a default password.
  for /f %%i in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"') do set "DBPW=%%i"
  for /f %%i in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"') do set "S3PW=%%i"
  powershell -NoProfile -Command ^
    "$p='.env.production'; $c=[IO.File]::ReadAllText($p); $c=$c.Replace('change-me-before-first-boot','!DBPW!'); $c=$c.Replace('STORAGE_SECRET_ACCESS_KEY=!DBPW!','STORAGE_SECRET_ACCESS_KEY=!S3PW!'); [IO.File]::WriteAllText($p,$c)"
  echo   [OK] .env.production created with random passwords
) else (
  echo   [OK] .env.production already exists - keeping your settings
)

REM ---- Build and start ---------------------------------------------------
echo.
echo   [..] Building images. The FIRST run takes 10-20 minutes.
echo        Later runs are near-instant because Docker caches the layers.
echo.

docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production up -d --build
if errorlevel 1 (
  echo.
  echo   [X] The stack failed to start. The error is above.
  echo       Logs:  docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production logs
  echo.
  pause
  exit /b 1
)

REM ---- Verify ------------------------------------------------------------
echo.
echo   [..] Waiting for services to become healthy
timeout /t 25 /nobreak >nul

bash scripts/prod-check.sh
echo.
echo   ============================================================
echo     Seller app     http://localhost:3000
echo     Browse listings http://localhost:3000/browse
echo     Admin panel    http://localhost:3001
echo     Email inbox    http://localhost:8025
echo   ============================================================
echo.
echo     API docs are OFF in this mode (ENV=staging in .env.production
echo     closes /docs the same way a real deploy would - see
echo     packages/py/trustlens-shared/.../config/settings.py:expose_docs).
echo     For Swagger, run start.bat instead.
echo.
echo     Demo logins are in CREDENTIALS.dev.md
echo     Stop everything with prod-stop.bat
echo.
pause
