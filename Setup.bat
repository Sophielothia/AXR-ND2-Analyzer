@echo off
setlocal
cd /d "%~dp0"
echo AXR ND2 Analyzer - environment setup
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3,12), 'Python 3.12 or later is required'"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Setup complete. Double-click Start.bat to launch.
pause
exit /b 0
:failed
echo.
echo Setup failed. Install Python 3.12+ from python.org, then rerun Setup.bat.
pause
exit /b 1
