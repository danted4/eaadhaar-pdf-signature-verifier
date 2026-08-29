@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==^> eVerify setup
echo     Project: %CD%
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Error: python not found. Install Python 3.10+ from https://www.python.org/ and re-run.
  exit /b 1
)

for /f "tokens=*" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PY_VER=%%v
echo ==^> Using Python %PY_VER%

if not exist ".venv" (
  echo ==^> Creating virtual environment (.venv^)
  python -m venv .venv
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
