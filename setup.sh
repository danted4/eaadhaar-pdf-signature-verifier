#!/usr/bin/env bash
# End-to-end setup for eVerify (local e-Aadhaar PDF signature verifier).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PYTHON_DOWNLOAD_URL="https://www.python.org/downloads/"

echo "==> eVerify setup"
echo "    Project: $ROOT"
echo

# --- Python 3.10+ (python3, then python; skip a command that is too old) ---
echo "==> Checking Python"
PYTHON=""
SAW_PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" >/dev/null 2>&1; then
    SAW_PYTHON=1
    "$cmd" --version 2>/dev/null || true
    if "$cmd" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PYTHON="$cmd"
      break
    fi
  fi
done
if [[ -z "$PYTHON" ]]; then
  if [[ -n "$SAW_PYTHON" ]]; then
    echo "Error: Python is too old. Python 3.10+ is required." >&2
  else
    echo "Error: Python 3.10+ was not found (tried python3, then python)." >&2
  fi
  echo "Install it from ${PYTHON_DOWNLOAD_URL} and re-run this script." >&2
  exit 1
fi

PY_VER="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "==> Using $PYTHON (Python $PY_VER)"

# --- Virtual environment ---
if [[ ! -d .venv ]]; then
  echo "==> Creating virtual environment (.venv)"
  "$PYTHON" -m venv .venv
else
  echo "==> Virtual environment already exists"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing Python dependencies"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "==> CCA India trust roots (bundled with this repo)"
for cert in CCAIndia2022.cer CCAIndia2022SPL.cer; do
  if [[ ! -f "$cert" ]]; then
    echo "Error: $cert not found." >&2
    echo "Download India PKI root certificates from https://cca.gov.in/root_certificate.html" >&2
    echo "and place them in the project root, then re-run setup." >&2
    exit 1
  fi
  echo "    ✓ $cert"
done

chmod +x everify-app 2>/dev/null || true

echo
echo "==> Setup complete"
echo
echo "Start the viewer:"
echo "  ./everify-app"
echo
echo "Then open http://127.0.0.1:8765/ in your browser."
echo
echo "CLI validation (optional):"
echo "  .venv/bin/python verify_aadhaar.py /path/to/your.pdf -p YOUR_PASSWORD"
echo
