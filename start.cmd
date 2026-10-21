@echo off
rem StreamTurbo launcher (ADR-0006): driver check, uv bootstrap, frozen sync, doctor.
rem Everything it downloads stays inside this folder, so deleting the folder uninstalls it.
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%~dp0"
set "UV_VERSION=0.12.24"
rem Keep MIN_DRIVER and DRIVER_URL in step with src\streamturbo\doctor.py.
set "MIN_DRIVER=580"
set "DRIVER_URL=https://www.nvidia.com/Download/index.aspx"

if not defined UV_CACHE_DIR set "UV_CACHE_DIR=%ROOT%cache\uv"
set "UV_PYTHON_INSTALL_DIR=%ROOT%cache\python"
set "UV_PYTHON_PREFERENCE=only-managed"

rem --- 1. NVIDIA driver ---------------------------------------------------
set "DRIVER="
for /f "tokens=1 delims=." %%v in ('nvidia-smi --query-gpu^=driver_version --format^=csv^,noheader 2^>nul') do if not defined DRIVER set "DRIVER=%%v"
rem nvidia-smi prints its failures to stdout, so accept only a number.
if defined DRIVER for /f "delims=0123456789" %%x in ("%DRIVER%") do set "DRIVER="
if not defined DRIVER (
    echo [StreamTurbo] No NVIDIA driver was found. StreamTurbo needs an NVIDIA GPU ^(RTX 20 or newer^).
    echo [StreamTurbo] Install driver %MIN_DRIVER% or newer from %DRIVER_URL%
    goto :fail
)
if %DRIVER% LSS %MIN_DRIVER% (
    echo [StreamTurbo] NVIDIA driver %DRIVER% is too old. Version %MIN_DRIVER% or newer is required.
    echo [StreamTurbo] Update it from %DRIVER_URL%
    goto :fail
)
echo [StreamTurbo] NVIDIA driver %DRIVER% OK

rem --- 2. uv --------------------------------------------------------------
rem Always use the pinned uv in cache\bin, never whichever uv happens to be on PATH.
set "UV=%ROOT%cache\bin\uv.exe"
if exist "%UV%" "%UV%" --version 2>nul | findstr /b /c:"uv %UV_VERSION% " >nul && goto :sync
echo [StreamTurbo] Installing uv %UV_VERSION% into cache\bin ...
rem A PSModulePath inherited from PowerShell 7 breaks Windows PowerShell 5.1.
set "PSModulePath="
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:UV_INSTALL_DIR='%ROOT%cache\bin'; $env:UV_NO_MODIFY_PATH='1'; irm https://astral.sh/uv/%UV_VERSION%/install.ps1 | iex"
if not exist "%UV%" (
    echo [StreamTurbo] Could not install uv. Check the network connection and try again.
    goto :fail
)

rem --- 3. Environment -----------------------------------------------------
:sync
echo [StreamTurbo] Syncing the Python environment (the first run downloads several GB) ...
rem --inexact leaves a developer's dev tools in .venv instead of uninstalling them.
"%UV%" sync --frozen --no-dev --inexact
if errorlevel 1 (
    echo [StreamTurbo] The environment could not be synced.
    goto :fail
)

rem --- 4. Doctor ----------------------------------------------------------
"%UV%" run --no-sync streamturbo doctor
if errorlevel 1 goto :fail

endlocal
pause
exit /b 0

:fail
echo.
pause
endlocal
exit /b 1
