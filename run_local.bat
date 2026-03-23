@echo off
REM Delegates to run_local.ps1 (one place for port kill + venv + URLs).
cd /d "%~dp0" || exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local.ps1"
exit /b %ERRORLEVEL%
