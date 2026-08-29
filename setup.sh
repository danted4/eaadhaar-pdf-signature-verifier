#!/usr/bin/env bash
# End-to-end setup for eVerify (local e-Aadhaar PDF signature verifier).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> eVerify setup"
echo "    Project: $ROOT"
echo

# --- Python 3.10+ recommended ---
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found. Install Python 3.10+ and re-run." >&2
  exit 1
fi

PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "==> Using Python $PY_VER"

# --- Virtual environment ---
if [[ ! -d .venv ]]; then
  echo "==> Creating virtual environment (.venv)"
  python3 -m venv .venv
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
