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
REM Killed by PORT OWNERSHIP first, then by command line.
REM
REM Matching on the command line alone is not enough, and this cost an
REM afternoon to find: uvicorn --reload spawns a child worker whose command
REM line reads "from multiprocessing.spawn import spawn_main", with the word
REM uvicorn nowhere in it. Killing the parent left that child alive holding
REM port 8000, so the NEXT start.bat could not bind - and the only symptom
REM was that login silently stopped working.
REM
REM Whoever owns the port is who has to go, whatever it calls itself.
echo [1/3] Stopping API, worker, web and admin...
powershell -NoProfile -Command ^
  "foreach ($port in 3000,3001,8000) { Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }" 2>nul

REM The worker binds no port, so it is matched on its command line. Narrow
REM patterns on purpose: killing every python.exe would take out unrelated
REM work the user has open, which is a rude thing for a stop script to do.
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'trustlens_worker|uvicorn|multiprocessing.spawn' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul

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
