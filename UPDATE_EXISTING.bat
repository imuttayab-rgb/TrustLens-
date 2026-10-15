@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Open Git Bash in this extracted release and run:
  echo bash scripts/local/update-existing.sh "$HOME/Documents/TrustLens" trustlens
  echo This updates your existing installation and keeps its accounts, listings and chat.
  pause
  exit /b 0
)
bash scripts/local/update-existing.sh "%~1" "%~2"
set "result=%errorlevel%"
pause
exit /b %result%
