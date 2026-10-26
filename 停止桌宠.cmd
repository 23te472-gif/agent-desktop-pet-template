@echo off
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
".venv\Scripts\python.exe" -X utf8 maintenance.py --stop
