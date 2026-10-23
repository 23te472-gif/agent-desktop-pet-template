@echo off
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Python dependencies installed. See README for JavaScript libraries and your own model.
pause
exit /b 0
:fail
echo Installation failed. Install Windows x64 CPython 3.12 with the Python launcher.
pause
exit /b 1
