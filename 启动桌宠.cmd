@echo off
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
if not exist ".venv\Scripts\python.exe" (echo Install requirements into .venv first. & exit /b 2)
".venv\Scripts\python.exe" -X utf8 run.py %*
