@echo off
REM TrustLens - stop the production stack. Data is kept.
cd /d "%~dp0"
title TrustLens - stopping

echo.
echo   Stopping the TrustLens production stack...
echo.

docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production down

echo.
echo   Stopped. All data is kept - prod-start.bat brings it back.
echo.
echo   To delete the data as well:
echo     make prod-nuke
echo.
pause
