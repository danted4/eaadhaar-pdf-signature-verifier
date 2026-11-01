@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "PYTHON_DOWNLOAD_URL=https://www.python.org/downloads/"

echo ==^> eVerify setup
echo     Project: %CD%
echo.

echo ==^> Checking Python
set "PYTHON="

python3 --version >nul 2>&1
if not errorlevel 1 (
  python3 --version
  python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON=python3"
    goto :have_python
  )
)

python --version >nul 2>&1
if not errorlevel 1 (
  python --version
  python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON=python"
    goto :have_python
  )
)

echo Error: Python 3.10+ was not found (tried python3, then python).
echo If a Python command exists, it is too old. Python 3.10+ is required.
echo Install it from %PYTHON_DOWNLOAD_URL%
echo During setup, tick "Add python.exe to PATH", then re-run setup.bat.
exit /b 1

:have_python

for /f "tokens=*" %%v in ('"%PYTHON%" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PY_VER=%%v
echo ==^> Using %PYTHON% (Python %PY_VER%^)

if not exist ".venv" (
  echo ==^> Creating virtual environment (.venv^)
  "%PYTHON%" -m venv .venv
  if errorlevel 1 exit /b 1
) else (
  echo ==^> Virtual environment already exists
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 exit /b 1

echo ==^> Installing Python dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo ==^> CCA India trust roots (bundled with this repo^)
for %%f in (CCAIndia2022.cer CCAIndia2022SPL.cer) do (
  if not exist "%%f" (
    echo Error: %%f not found.
    echo Download India PKI root certificates from https://cca.gov.in/root_certificate.html
    echo and place them in the project root, then re-run setup.
    exit /b 1
  )
  echo     [ok] %%f
)

echo.
echo ==^> Setup complete
echo.
echo Start the viewer:
echo   everify-app.bat
echo.
echo Then open http://127.0.0.1:8765/ in your browser.
echo.
echo CLI validation (optional^):
echo   .venv\Scripts\python verify_aadhaar.py C:\path\to\your.pdf -p YOUR_PASSWORD
echo.

endlocal
