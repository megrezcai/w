@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0runtime\python.exe" (
  echo Portable Python runtime not found. Please extract the complete Windows package.
  pause
  exit /b 1
)
"%~dp0runtime\python.exe" -E -s -m surface_text.server
if errorlevel 1 pause
