@echo off
REM ============================================================
REM  TrustLens - stop everything
REM
REM  Stops the four dev servers and the containers, and frees
REM  every port. Database contents survive: this uses
REM  `compose down`, not `down -v`, so the volumes are kept.
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo  ============================================
echo   TrustLens - stopping
echo  ============================================
echo.

REM ---------- 1. Dev servers ----------
REM Matched on command line rather than image name: killing every
REM python.exe or node.exe would take out unrelated work the user
REM has open, which is a rude thing for a stop script to do.
echo [1/3] Stopping API, worker, web and admin...
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'uvicorn|trustlens_worker' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { $_.CommandLine -match 'next' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul

REM Close the four terminal windows start.bat opened.
taskkill /FI "WINDOWTITLE eq TrustLens API*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq TrustLens Worker*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq TrustLens Web*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq TrustLens Admin*" /T /F >nul 2>&1

REM ---------- 2. Containers ----------
echo [2/3] Stopping containers (your data is kept)...
docker compose -f docker/compose/docker-compose.dev.yml down 2>nul

REM ---------- 3. Verify ----------
echo [3/3] Checking ports...
powershell -NoProfile -Command ^
  "foreach ($p in 3000,3001,8000,5432,6379,8025,9001) { $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue; if ($c) { Write-Host ('   ' + $p + ' STILL IN USE') } else { Write-Host ('   ' + $p + ' free') } }"

echo.
echo  ============================================
echo   Stopped. Database contents preserved.
echo  ============================================
echo.
echo   To wipe the database as well:
echo     docker compose -f docker/compose/docker-compose.dev.yml down -v
echo.
pause
