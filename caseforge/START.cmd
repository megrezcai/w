@echo off
setlocal
cd /d "%~dp0"
if exist "CaseForge.exe" (
  CaseForge.exe %*
  goto done
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 run.py %*
  goto done
)
where python >nul 2>nul
if not errorlevel 1 (
  python run.py %*
  goto done
)
echo Install Python 3.10 or newer from https://www.python.org/downloads/windows/
echo Enable "Add python.exe to PATH" during installation, then run this file again.
:done
pause
