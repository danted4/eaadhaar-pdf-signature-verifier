# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local-only tool that validates the UIDAI digital signature in a password-protected e-Aadhaar PDF against bundled CCA India trust roots (`certs/`), then draws an Acrobat-style green "Signature valid" stamp on a canvas overlay. Python stdlib HTTP server + pyHanko on the backend, vanilla JS + vendored pdf.js 3.11.174 on the frontend. No build step, no npm, no framework.

## Commands

```bash
./setup.sh                      # one-time: creates .venv, installs requirements.txt (pinned), checks certs/
./everify-app [PORT]            # runs app/server.py on 127.0.0.1:8765 (or PORT); opens a browser
.venv/bin/python verify_aadhaar.py file.pdf -p PASSWORD   # CLI; exits 0 only if VALID

# Full test suite (stdlib unittest; no pytest)
.venv/bin/python -m unittest discover -s tests -v

# Single file / class / test: tests import `support` and `pdf_fixtures` as top-level
# modules, so run from inside tests/ (or keep -s tests with -p)
.venv/bin/python -m unittest discover -s tests -p test_http.py
cd tests && ../.venv/bin/python -m unittest test_http.ParseHelpersTests.test_content_length_rejects_negative
```

There is no linter or formatter configured.

## Architecture

**Two-phase flow, two different byte streams.** This is the core design constraint:

1. `POST /api/preview` (multipart `pdf` + `password`) → `verify.preview_pdf_bytes` decrypts with pikepdf into `viewBytes` for pdf.js to render, and returns signature-widget geometry. The server stores both `viewBytes` and the **original** upload in an in-memory session (`SESSIONS`, mutex-guarded, 30-min TTL, keyed by uuid).
2. `GET /api/pdf/<sid>` serves the decrypted `viewBytes` to pdf.js.
3. User clicks the `?` widget → `POST /api/validate {sessionId}` → `verify.validate_uploaded_bytes` runs pyHanko on the **original encrypted bytes** (decrypting in pyHanko's reader only).

Validation must never run on pikepdf-resaved bytes: re-saving breaks signature byte-range coverage. `validate_decrypted_bytes` exists but is a trap for this reason. `/api/verify` is a legacy one-shot (preview + validate together).

**Widget geometry for the stamp.** `verify._appearance` regex-parses the Acrobat n0–n4 signature appearance layers (`/AP /N /FRM /n1 /n2 /n4`) to extract transform matrices, bbox, font sizes and n2 text lines, with hardcoded fallbacks when parsing fails. The frontend uses this plus `rect`/`mediaBox`/`pageIndex` to position its own rendering over the native `?` stamp.

**Frontend.** `app/static/viewer.js` (ES module) drives upload → preview → click-to-validate → modal → overlay → print (re-renders at 600 DPI into a hidden print store). `stamp-render.js` is a tiny PDF content-stream interpreter (`execPdfStream`) plus the green tick/stamp drawing (`drawStamp`). `index.html` loads `viewer.js?v=N`; bump the query string when changing frontend JS so browsers don't serve a stale copy.

**Stamp config is duplicated on purpose.** The locked layout is `STAMP_CONFIG` in `viewer.js`; `app/stamp-config.default.json` is the reference export. `tests/test_stamp_config.py` extracts `STAMP_CONFIG` with a brace-matching regex and asserts key overlap matches the JSON, so keep that object a plain JSON-like literal and update both together. `prototype/` (the stamp tuning lab, served at `/prototype/` if present) is gitignored and local-only. The CSP applies there too, so any inline `<script>`/`<style>`/`style=` in the lab must live in files under `prototype/`.

**CLI** (`verify_aadhaar.py`) puts `app/` on `sys.path` and calls the same `validate_uploaded_bytes`; there is deliberately only one validation path.

## Tests

The suite is hermetic: no network, no real `.venv`, no real Aadhaar.

- `tests/pdf_fixtures.py` builds an in-process RSA CA + leaf, signs a blank PDF with pyHanko, encrypts it, and can `tamper()` it. Tests point validation at the synthetic CA with `mock.patch.object(verify, "CERTS_DIR", tmp)`; the fake root is written as `CCAIndia2022.cer` so `load_trust_roots` picks it up.
- HTTP tests bind a real `ThreadingHTTPServer` on `127.0.0.1:0`.
- Shell launcher tests (`test_setup_sh.py`, `test_everify_app.py`) run the real scripts under a stripped `PATH` with a fake `python`/`python3` (`tests/python_stub.sh`, controlled by `PYTHON_STUB_VERSION`/`_LOG`/`_EXIT`) so they can check interpreter selection and version gating.
- Windows `.bat` files are checked statically (`test_windows_scripts.py`), not executed.

## Invariants enforced by tests

- `setup.sh` and `everify-app` must be LF; `.bat` files must be CRLF (`.gitattributes` enforces this; editors that rewrite line endings will fail `test_line_endings.py`).
- Launchers try `python3` then `python` (sh) / `python.exe` then `python3.exe` (bat), require 3.10+, and the `.bat` launcher must propagate the exit code outside the `if` block (no `%ERRORLEVEL%` inside parentheses).
- No CDN references: pdf.js must load from `/static/pdfjs/` (`test_pdfjs.py`).
- `getDocument` must keep `isEvalSupported: false`. The CSP added in `Handler.end_headers`, which covers every response including `send_error` pages, must keep `script-src`/`style-src` at `'self'`, with no `unsafe-eval`/`unsafe-inline` (`test_pdfjs.py`, `test_http.py`). Together these close CVE-2024-4367, a forged PDF faking the green tick.
- No inline styles in `app/static/*.js` or `index.html`: no `<style>` blocks, no `style=` attributes, no `setAttribute("style")`. The CSP silently drops them. Use CSSOM (`el.style.x`) or a static stylesheet; the print iframe loads `app/static/print-frame.css` and refuses to print if that file fails to load.
- Upload `Content-Length` must be `0..20 MiB`; `/api/validate` JSON bodies are capped at 64 KiB.

## Privacy

`*.pdf` is gitignored because real e-Aadhaar files sit in the working tree during local testing. Never commit, attach, or quote real e-Aadhaar PDFs, passwords, or Aadhaar numbers; use `pdf_fixtures` for anything test-related. Server must stay bound to `127.0.0.1`.

## Releases

Version lives in the README header line, the README "Changelog" section, and `CHANGELOG.md` (Keep a Changelog format with link refs at the bottom). Update all three together.
