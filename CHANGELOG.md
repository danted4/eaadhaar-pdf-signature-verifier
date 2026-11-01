# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- CCA India trust roots live in `certs/`; stamp reference config lives in `app/stamp-config.default.json`

## [2.3.1] - 2026-11-01

### Added

- Hermetic `unittest` suite for setup/launch scripts, HTTP handlers, CLI, and signature validation (synthetic CA; no real e-Aadhaar)
- Vendored **pdf.js 3.11.174** under `app/static/pdfjs/` so preview does not load scripts from a CDN
- `.gitattributes` so shell scripts stay LF and `.bat` files stay CRLF

### Changed

- Setup tries `python3`, then `python`, and skips a command older than 3.10
- CLI verifier (`verify_aadhaar.py`) uses `app.verify.validate_uploaded_bytes` instead of a second validation loop
- README documents local pdf.js, offline-after-setup, and the test command

### Security

- Reject upload `Content-Length` unless `0 <= length <= 20 MiB` (negative lengths no longer read until EOF)
- Cap `/api/validate` JSON bodies at 64 KiB
- Session store is mutex-protected; invalid ports and bind failures exit with a clear error

### Fixed

- `setup.sh` stored as CRLF could not parse on macOS/Linux
- `everify-app.bat` reported exit code 0 when the Python process failed (`%ERRORLEVEL%` inside parentheses)

## [1.0.0] - 2026-08-29

### Added

- Local web viewer at `http://127.0.0.1:8765/` for password-protected e-Aadhaar PDFs
- Published as **eaadhaar-pdf-signature-verifier** with SEO README and GitHub topics
- Preview-first flow: native `?` stamp from the PDF, then click-to-verify
- Cryptographic validation via pyHanko against bundled **CCA India 2022** trust roots
- Verification details popup (signer, signing time, trust chain, integrity checks)
- Acrobat-style green **Signature valid** stamp overlay (canvas only; original PDF unchanged)
- High-DPI rendering for sharp preview and print
- CLI verifier: `verify_aadhaar.py`
- One-shot setup: `setup.sh` (macOS/Linux) and `setup.bat` (Windows)
- Launch scripts: `everify-app` / `everify-app.bat`
- Platform setup docs in README
- Step-by-step README with mermaid diagrams and disclaimers
- Reference stamp config: `stamp-config.default.json`

### Security

- Validation runs on original uploaded bytes (in-memory decrypt only) to preserve signature integrity
- Server binds to `127.0.0.1` only; no cloud upload
- In-memory sessions expire after 30 minutes

### Fixed

- Incorrect PDF password now returns a clear error instead of crashing the preview server
- Fixed blank screen after clicking OK on the verification popup
- Improved print output with background 600 DPI rendering while keeping screen preview responsive
- Print output no longer includes browser title, URL, date, or page-number headers/footers

### Removed

- Legacy `everify.py` monolithic entry point (use `./everify-app` instead)
- Prototype stamp lab from the public repository (local dev only, gitignored)

[Unreleased]: https://github.com/danted4/eaadhaar-pdf-signature-verifier/compare/v2.3.1...HEAD
[2.3.1]: https://github.com/danted4/eaadhaar-pdf-signature-verifier/releases/tag/v2.3.1
[1.0.0]: https://github.com/danted4/eaadhaar-pdf-signature-verifier/releases/tag/v1.0.0
