@echo off
setlocal EnableExtensions
cd /d "%~dp0"
py -3 -c "import sys; raise SystemExit(sys.version_info < (3,10))"
if errorlevel 1 goto failed
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip --isolated install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Double-click Start.cmd.
pause
exit /b 0
:failed
echo Setup failed. Python 3.10+ with Tk is required. No other project environment was modified.
pause
exit /b 1
