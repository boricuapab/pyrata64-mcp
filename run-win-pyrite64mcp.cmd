@echo off
setlocal
where pwsh.exe >nul 2>nul
if errorlevel 1 (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-win-pyrite64mcp.ps1" %*
) else (
    pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-win-pyrite64mcp.ps1" %*
)
set "launcherExit=%errorlevel%"
if not "%launcherExit%"=="0" pause
exit /b %launcherExit%
