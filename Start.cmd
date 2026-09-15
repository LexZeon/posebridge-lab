@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%CD%\src;%CD%\.runtime-deps"
if exist "%CD%\.venv\Scripts\python.exe" (
    set "POSEBRIDGE_PYTHON=%CD%\.venv\Scripts\python.exe"
    goto launch
)
rem Optional machine-local interpreter configuration is never committed.
if exist "%CD%\Runtime.local.cmd" call "%CD%\Runtime.local.cmd"
if defined POSEBRIDGE_PYTHON goto launch
echo First run: double-click Setup.cmd to create this project's Python environment.
pause
exit /b 1
:launch
"%POSEBRIDGE_PYTHON%" -m posebridge_lab %*
if errorlevel 1 (
    echo Startup failed. Check the error above and read Start.md.
    pause
    exit /b 1
)
