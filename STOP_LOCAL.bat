@echo off
setlocal
cd /d "%~dp0"
where bash >nul 2>nul
if errorlevel 1 (
  echo Install Git for Windows with Git Bash on PATH, or open Git Bash in this folder.
  pause
  exit /b 1
)
bash scripts/local/stop.sh
set "result=%errorlevel%"
if not "%result%"=="0" echo Command stopped. Read the error above.
pause
exit /b %result%
