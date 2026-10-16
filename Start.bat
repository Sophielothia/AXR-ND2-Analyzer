@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Please run Setup.bat first to install the environment.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" gui.py
if errorlevel 1 pause
