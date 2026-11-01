#!/bin/bash
# Hermetic stand-in for python/python3 used only by tests.
# Env:
#   PYTHON_STUB_VERSION  e.g. 3.12 or 3.9 (default 3.12)
#   PYTHON_STUB_LOG      append one argv line per invocation
#   PYTHON_STUB_EXIT     status when asked to run a .py file (default 0)
#   PYTHON_STUB_SELF     wrapper path to copy into a fake venv

if [[ -n "${PYTHON_STUB_LOG:-}" ]]; then
  printf '%s\n' "${PYTHON_STUB_SELF:-$0} $*" >> "$PYTHON_STUB_LOG"
fi

VERSION="${PYTHON_STUB_VERSION:-3.12}"
MAJOR="${VERSION%%.*}"
REST="${VERSION#*.}"
MINOR="${REST%%.*}"

if [[ "${1:-}" == "--version" ]]; then
  echo "Python ${MAJOR}.${MINOR}.0"
  exit 0
fi

if [[ "${1:-}" == "-c" ]]; then
  code="${2:-}"
  case "$code" in
    *'sys.version_info >= (3, 10)'*)
      if [[ "$MAJOR" -gt 3 || ( "$MAJOR" -eq 3 && "$MINOR" -ge 10 ) ]]; then
        exit 0
      fi
      exit 1
      ;;
    *'version_info.major'*)
      echo "${MAJOR}.${MINOR}"
      exit 0
      ;;
  esac
  echo "python stub: unexpected -c: $code" >&2
  exit 90
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
  dest="${3:-.venv}"
  mkdir -p "$dest/bin"
  abs="$(cd "$dest" && pwd)"
  printf '%s\n' \
    "export VIRTUAL_ENV=\"$abs\"" \
    "export PATH=\"\$VIRTUAL_ENV/bin:\$PATH\"" \
    > "$abs/bin/activate"
  self="${PYTHON_STUB_SELF:-$0}"
  cp "$self" "$abs/bin/python"
  cp "$self" "$abs/bin/python3"
  chmod +x "$abs/bin/python" "$abs/bin/python3"
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "pip" ]]; then
  exit 0
fi

for arg in "$@"; do
  case "$arg" in
    *.py)
      exit "${PYTHON_STUB_EXIT:-0}"
      ;;
  esac
done

echo "python stub: unexpected argv: $*" >&2
exit 90
