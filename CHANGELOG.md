# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Errors after a PDF is open are now visible. Session expiry, a stopped server, validation errors, a PDF that pdf.js cannot display, and print failures show as an amber line in the top bar instead of silently resetting it. The bar keeps its verdict colour, so an app error is never mistaken for an invalid signature
- An INVALID result no longer names "CCA India 2022" as the trust anchor when no chain to it was established; it shows "Not established"
- `/api/validate` returns 400 for a body that is not a JSON object, has a non-string `sessionId`, or is not UTF-8, instead of dropping the connection
- Clicking Print repeatedly no longer leaves the page title blank or stacks print frames
- "Cannot reach the server" is now detected in every browser (Safari reported its raw "Load failed")
- The "?" in the preview bar icon is centred

### Changed

- An INVALID result shows one short reason in the popup and the bar, e.g. "Reason: signer certificate expired (2029-02-03)" or "Reason: document changed after signing". The API report gains a `failureReason` field
- The session-expired message says what to do: click "Open another" and open the PDF again
- No em dashes in UI text

## [2.3.3] - 2026-11-22

### Security

- Disable pdf.js eval (`isEvalSupported: false`) to close CVE-2024-4367, where a crafted font in a PDF could run script in the viewer and fake the green tick
- Send a strict Content-Security-Policy on every response, including stdlib error pages (`script-src 'self'`, `style-src 'self'`, no `'unsafe-eval'` or `'unsafe-inline'`, `frame-ancestors 'none'`), so the browser refuses eval even if pdf.js tried
- Send `X-Content-Type-Options: nosniff`, since `/api/pdf/<sid>` serves uploaded bytes

### Changed

- The print iframe loads `app/static/print-frame.css` and is styled through CSSOM instead of inline styles, which the CSP now blocks
- Print is refused with an error if `print-frame.css` cannot load (for example, the server was stopped), instead of printing unstyled 600 DPI images

## [2.3.2] - 2026-11-01

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

[2.3.3]: https://github.com/danted4/eaadhaar-pdf-signature-verifier/releases/tag/v2.3.3
[2.3.2]: https://github.com/danted4/eaadhaar-pdf-signature-verifier/releases/tag/v2.3.2
[2.3.1]: https://github.com/danted4/eaadhaar-pdf-signature-verifier/releases/tag/v2.3.1
[1.0.0]: https://github.com/danted4/eaadhaar-pdf-signature-verifier/releases/tag/v1.0.0
