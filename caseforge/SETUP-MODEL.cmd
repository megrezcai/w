@echo off
setlocal
cd /d "%~dp0"
echo Select the base model. The first run downloads several GB.
echo 1. Qwen3 8B - recommended for a PC with 16GB or more RAM
echo 2. Qwen3 4B - lower memory use, weaker negotiation understanding
set "CASEFORGE_BASE=qwen3:8b"
choice /c 12 /n /m "Choose 1 or 2: "
if errorlevel 2 set "CASEFORGE_BASE=qwen3:4b"
call START.cmd --setup-model --base-model "%CASEFORGE_BASE%"
