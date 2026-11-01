@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  echo Error: .venv not found. Run setup.bat first.
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "app\server.py" %*
  exit /b %ERRORLEVEL%
)

if exist ".venv\Scripts\python3.exe" (
  ".venv\Scripts\python3.exe" "app\server.py" %*
  exit /b %ERRORLEVEL%
)

echo Error: Python was not found in .venv (tried python.exe, then python3.exe).
echo Run setup.bat first. If Python is missing, install it from https://www.python.org/downloads/
echo During setup, tick "Add python.exe to PATH".
exit /b 1
