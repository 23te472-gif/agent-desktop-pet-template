@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" setup_check.py
) else (
  py -3 setup_check.py
)
pause
