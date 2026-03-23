@echo off
REM Spusteni: dvojklik nebo z cmd. Pri chybe okno zustane otevrene (pause).
cd /d "%~dp0" || (
    echo [CHYBA] Nepodarilo se prepnout do slozky skriptu.
    pause
    exit /b 1
)

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

where powershell.exe >nul 2>&1 || (
    echo [CHYBA] powershell.exe neni v PATH.
    pause
    exit /b 1
)

echo Spoustim run_local.ps1 ...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local.ps1" -ProjectRoot "%ROOT%"
set "EC=%ERRORLEVEL%"

if %EC% neq 0 (
    echo.
    echo [run_local.bat] Skript skoncil s kodem %EC%. Vyse je vystup z PowerShellu.
    pause
)

exit /b %EC%
