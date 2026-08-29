# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

### Removed

- Legacy `everify.py` monolithic entry point (use `./everify-app` instead)
- Prototype stamp lab from the public repository (local dev only, gitignored)

[1.0.0]: https://github.com/danted4/eaadhaar-pdf-signature-verifier/releases/tag/v1.0.0
