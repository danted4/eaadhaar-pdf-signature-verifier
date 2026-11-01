# e-Aadhaar PDF Signature Verifier

**Current release: [v2.3.1](https://github.com/danted4/eaadhaar-pdf-signature-verifier/releases/tag/v2.3.1)** · [Changelog](CHANGELOG.md)

**Local e-Aadhaar (Aadhar) PDF digital signature validation** — pyHanko, CCA India 2022, Acrobat-style green tick. No upload. Not affiliated with UIDAI or Adobe.

Validate the **UIDAI digital signature** embedded in your downloaded e-Aadhaar PDF using India's **CCA PKI** trust roots. Everything runs **on your machine**. No cloud, no account.

> **Keywords:** e-Aadhaar, Aadhaar, Aadhar, UIDAI, PDF signature, digital signature, PKCS#7, pyHanko, CCA India, India PKI, Acrobat alternative, green tick, offline verification.

## Table of contents

- [Why this exists](#why-this-exists)
- [Quick start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [One-time setup](#one-time-setup)
  - [Run the viewer](#run-the-viewer)
- [Platform commands](#platform-commands)
- [How to verify your e-Aadhaar (step by step)](#how-to-verify-your-e-aadhaar-step-by-step)
  - [Before you start](#before-you-start)
  - [Part A — One-time install](#part-a--one-time-install)
  - [Part B — Verify in the browser (recommended)](#part-b--verify-in-the-browser-recommended)
  - [Part C — CLI smoke test (optional)](#part-c--cli-smoke-test-optional)
  - [What “valid” means](#what-valid-means)
  - [Troubleshooting](#troubleshooting)
  - [Usage flow (diagram)](#usage-flow-diagram)
- [How validation works](#how-validation-works)
  - [Checks performed (same family as Acrobat)](#checks-performed-same-family-as-acrobat)
- [Acrobat comparison](#acrobat-comparison)
- [Stamp configuration](#stamp-configuration)
- [Project layout](#project-layout)
- [Security & privacy](#security--privacy)
- [Disclaimers](#disclaimers)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [License](#license)
- [Star History](#star-history)

---

## Why this exists

Photocopy shops and government workflows often use **Adobe Acrobat** to:

1. Open a password-protected e-Aadhaar PDF  
2. **Validate** the digital signature (PKCS#7 / certificate chain)  
3. Show the green **“Signature valid”** stamp  
4. Print a copy that looks “verified”

That works, but Acrobat is **heavy**, often **paid**, and **overkill** if you only need signature validation and a correct validity mark. macOS Preview and most browsers show a **?** for Indian PKI signatures even when the document is **cryptographically valid** — they simply do not ship the **CCA India** root certificates or full Adobe-style signature rendering.

This tool is a small, local alternative to Adobe Acrobat for Indian PKI–signed PDFs. It:

- Performs the same **class of cryptographic checks** as Acrobat (via [pyHanko](https://github.com/MatthiasValvekens/pyHanko))  
- Renders an **Acrobat-style green tick** overlay (tuned in the stamp lab)  
- Never modifies your original PDF  

---

## Quick start

### Prerequisites

- **Python 3.10+** (3.11 or 3.12 recommended)  
- macOS, Linux, or Windows with a browser  

### One-time setup

**macOS / Linux**

```bash
git clone https://github.com/danted4/eaadhaar-pdf-signature-verifier.git
cd eaadhaar-pdf-signature-verifier
chmod +x setup.sh
./setup.sh
```

**Windows** (Command Prompt or PowerShell)

```bat
git clone https://github.com/danted4/eaadhaar-pdf-signature-verifier.git
cd eaadhaar-pdf-signature-verifier
setup.bat
```

### Run the viewer

**macOS / Linux**

```bash
./everify-app
```

**Windows**

```bat
everify-app.bat
```

Open **http://127.0.0.1:8765/** in your browser. Your terminal should show `e-Aadhaar PDF Signature Verifier at http://127.0.0.1:8765/`.

---

## Platform commands

All commands assume you have already cloned the repo and are inside the `eaadhaar-pdf-signature-verifier` folder.

| Task | macOS | Linux | Windows |
|------|-------|-------|---------|
| **Check Python** | `python3 --version` or `python --version` | `python3 --version` or `python --version` | `python3 --version` or `python --version` |
| **One-time setup** | `chmod +x setup.sh && ./setup.sh` | `chmod +x setup.sh && ./setup.sh` | `setup.bat` |
| **Start viewer** | `./everify-app` | `./everify-app` | `everify-app.bat` |
| **Open UI** | http://127.0.0.1:8765/ | http://127.0.0.1:8765/ | http://127.0.0.1:8765/ |
| **Stop server** | `Ctrl+C` in the terminal running the viewer | `Ctrl+C` | `Ctrl+C` in the Command Prompt / PowerShell window |

> **Optional:** CLI smoke test — see [Part C](#part-c--cli-smoke-test-optional).

### macOS — full copy-paste

```bash
git clone https://github.com/danted4/eaadhaar-pdf-signature-verifier.git
cd eaadhaar-pdf-signature-verifier
chmod +x setup.sh && ./setup.sh
./everify-app
```

### Linux — full copy-paste

```bash
git clone https://github.com/danted4/eaadhaar-pdf-signature-verifier.git
cd eaadhaar-pdf-signature-verifier
chmod +x setup.sh && ./setup.sh
./everify-app
```

### Windows — full copy-paste

Command Prompt or PowerShell:

```bat
git clone https://github.com/danted4/eaadhaar-pdf-signature-verifier.git
cd eaadhaar-pdf-signature-verifier
setup.bat
everify-app.bat
```

> **Python note:** Setup tries `python3`, then `python`, and skips a command older than 3.10. If neither is Python 3.10+, install it from [python.org/downloads](https://www.python.org/downloads/). On Windows, tick **“Add python.exe to PATH”** during setup.

---

## How to verify your e-Aadhaar (step by step)

### Before you start

You need:

1. An **e-Aadhaar PDF** downloaded from the [UIDAI portal](https://myaadhaar.uidai.gov.in/) (or the official mAadhaar app export).
2. The **PDF password** you chose when downloading (often your name in `CAPS` + birth year, e.g. `NAME1990`). This is **not** your Aadhaar number.
3. A computer with **Python 3.10+** and a web browser.

e-Aadhaar PDF Verifier checks the **digital signature** UIDAI embedded in that PDF. It does **not** log in to UIDAI or verify your identity online.

---

### Part A — One-time install

**macOS / Linux**

| Step | What to do |
|------|------------|
| **1** | Open a terminal |
| **2** | Clone the repo: `git clone https://github.com/danted4/eaadhaar-pdf-signature-verifier.git` |
| **3** | Enter the folder: `cd eaadhaar-pdf-signature-verifier` |
| **4** | Run setup: `chmod +x setup.sh && ./setup.sh` |
| **5** | Wait until you see **“Setup complete”** |

**Windows**

| Step | What to do |
|------|------------|
| **1** | Open Command Prompt or PowerShell |
| **2** | Clone the repo: `git clone https://github.com/danted4/eaadhaar-pdf-signature-verifier.git` |
| **3** | Enter the folder: `cd eaadhaar-pdf-signature-verifier` |
| **4** | Run setup: `setup.bat` |
| **5** | Wait until you see **“Setup complete”** |

If setup fails, run `python3 --version` or `python --version` and confirm it is 3.10 or newer. If neither command works, install Python from [python.org/downloads](https://www.python.org/downloads/).

---

### Part B — Verify in the browser (recommended)

Steps **2–10** are the same on every platform (browser UI). Only **step 1** (start the server) differs — see [Platform commands](#platform-commands).

| Step | What to do | What you should see |
|------|------------|---------------------|
| **1** | Start the viewer (see platform table above) | Terminal prints the local URL |
| **2** | Open **http://127.0.0.1:8765/** in Chrome, Firefox, or Safari | Upload screen |
| **3** | Click **Choose PDF** and select your e-Aadhaar `.pdf` file | File name appears below the button |
| **4** | Type your **PDF password** in the password field | — |
| **5** | Click **Preview** | Document opens; brown bar says *“Preview — click the ? mark to verify”* |
| **6** | Find the **yellow ?** signature box (top of the Aadhaar page) and **click it** | Brief “Verifying signature…” then a **verification popup** |
| **7** | Read the popup (signer, signing time, CCA trust chain, how validation works) | UIDAI signer, **CCA India 2022** trust anchor, integrity checks |
| **8** | If valid → click **OK**. If invalid → click **Close** | Valid: blue bar + green **“Signature valid”** tick on the document |
| **9** | (Optional) Click **Print** for a paper copy | Print uses the on-screen view with the green tick overlay |
| **10** | Stop the server with `Ctrl+C`, or click **Open another** to verify a different PDF | — |

**Important:** The green tick is drawn **on screen only** for preview/print. Your original PDF file on disk is **never modified**.

---

### Part C — CLI smoke test *(optional)*

> **Optional.** Quick terminal check — same cryptographic validation as Part B, without the browser or green-tick UI. For normal use, stick with [Part B](#part-b--verify-in-the-browser-recommended).

**macOS / Linux:** `.venv/bin/python verify_aadhaar.py ~/Downloads/EAadhaar_xxxx.pdf -p YOUR_PASSWORD`  
**Windows:** `.venv\Scripts\python verify_aadhaar.py C:\Users\You\Downloads\EAadhaar_xxxx.pdf -p YOUR_PASSWORD`

Success ends with **`Bottom line: VALID`**.

---

### What “valid” means

- UIDAI’s certificate signed the PDF and the signature **has not been tampered with**
- The certificate chain reaches **CCA India 2022** (India’s root CA), using roots bundled in this project
- The **date on the stamp** is when UIDAI signed the file, **not** when you ran e-Aadhaar PDF Verifier

This is the same **kind** of check Adobe Acrobat performs for “Signature valid” on an e-Aadhaar PDF.

---

### Troubleshooting

| Problem | macOS / Linux | Windows |
|---------|---------------|---------|
| `Cannot reach the server` | Run `./everify-app` first | Run `everify-app.bat` first |
| `python3` / `python` not found | Install 3.10+ from [python.org/downloads](https://www.python.org/downloads/); setup tries `python3` then `python` | Same; tick **Add python.exe to PATH** |
| `PDF is password-protected` / wrong password | Use UIDAI download password, not Aadhaar number | Same |
| `No digital signature found` | File may not be a signed e-Aadhaar PDF | Same |
| Preview shows `?` but won’t turn green | Click the signature box; read popup for **INVALID** | Same |
| macOS Preview shows `?` | Expected — use e-Aadhaar PDF Verifier instead | N/A |

---

### Usage flow (diagram)

1. **Choose PDF** — your password-protected e-Aadhaar file  
2. Enter the **PDF password** (the one you set when downloading from UIDAI)  
3. Click **Preview** — the document opens with the native **?** stamp from the file  
4. **Click the ?** signature area — e-Aadhaar PDF Verifier validates locally and shows a details popup  
5. Click **OK** — the green **Signature valid** stamp is drawn (canvas overlay only)  
6. **Print** — original file on disk is unchanged  

```mermaid
flowchart LR
  A[Choose PDF + password] --> B[Preview]
  B --> C[Native ? stamp from PDF]
  C --> D[Click signature]
  D --> E[Local pyHanko validation]
  E --> F{Valid?}
  F -->|Yes| G[Details popup → OK]
  G --> H[Green tick overlay]
  F -->|No| I[Details popup → Close]
  H --> J[Print / save screenshot]
```

---

## How validation works

e-Aadhaar PDF Verifier is **not** UIDAI authentication (no OTP, no biometric API, no Aadhaar number lookup). It only verifies the **embedded digital signature** on a PDF you already have.

```mermaid
sequenceDiagram
  participant U as Your browser
  participant S as e-Aadhaar PDF Verifier server (localhost)
  participant P as pyHanko
  participant C as CCA India roots

  U->>S: Upload PDF + password (preview)
  S->>S: Decrypt in memory for display only
  S-->>U: PDF pages + signature widget position

  U->>S: Click ? → validate
  S->>P: Validate original file bytes
  P->>P: Extract PKCS#7 signature
  P->>P: Verify SHA-256 digest + RSA signature
  P->>C: Build chain to CCA India 2022 root
  P-->>S: VALID / INVALID + signer time
  S-->>U: Report popup + widget metadata
  U->>U: Draw green tick overlay if valid
```

### Checks performed (same family as Acrobat)

| Check | Meaning |
|--------|---------|
| **Digest integrity** | SHA-256 hash of the signed byte ranges matches the signature |
| **Signature mechanism** | RSA (PKCS#1 v1.5) over the digest |
| **Certificate chain** | Signer cert → intermediates → **CCA India 2022** trust anchor |
| **Coverage** | Signature covers the entire file (no disallowed changes) |
| **Signing time** | Timestamp **reported by the signer** at signing (shown on the stamp) |

The date on the green stamp is **when UIDAI signed the PDF**, not when you ran e-Aadhaar PDF Verifier.

Trust roots shipped with this project (under `certs/`):

- `certs/CCAIndia2022.cer`  
- `certs/CCAIndia2022SPL.cer`  

Public certificates from [India PKI / CCA](https://cca.gov.in/root_certificate.html).

---

## Acrobat comparison

| | Adobe Acrobat | e-Aadhaar PDF Verifier |
|---|---------------|---------|
| Validates Indian PKI / UIDAI chain | Yes | Yes (pyHanko + CCA roots) |
| Green “Signature valid” appearance | Yes | Yes (custom renderer, stamp lab tuned) |
| Modifies original PDF | No (validation is read-only) | No (overlay is canvas-only) |
| Install size / cost | Large, often subscription | Small Python app, MIT license |
| Runs offline | Yes | Yes after setup (localhost; pdf.js is vendored) |
| UIDAI authentication API | No | No |

---

## Stamp configuration

Locked green-tick layout lives in `STAMP_CONFIG` inside `app/static/viewer.js`. Reference export: [`app/stamp-config.default.json`](app/stamp-config.default.json).

The interactive stamp tuning lab (`prototype/`) is **local development only** and is not included in the public repository.

---

## Project layout

```
eaadhaar-pdf-signature-verifier/
├── app/
│   ├── server.py          # Local HTTP server (127.0.0.1:8765)
│   ├── verify.py          # pyHanko validation + widget geometry
│   ├── stamp-config.default.json
│   └── static/            # Viewer UI, stamp renderer, vendored pdf.js 3.11.174
├── certs/                 # India PKI trust roots (public)
├── everify-app            # Launch viewer (macOS / Linux)
├── everify-app.bat        # Launch viewer (Windows)
├── setup.sh               # One-time setup (macOS / Linux)
├── setup.bat              # One-time setup (Windows)
├── verify_aadhaar.py      # CLI verifier (uses app.verify)
├── tests/                 # Hermetic unittest suite
├── CHANGELOG.md
└── requirements.txt
```

---

## Security & privacy

- **Local only** — server binds to `127.0.0.1`; PDF bytes stay on your machine. The viewer does not load scripts from a CDN: **pdf.js 3.11.174** is vendored at `app/static/pdfjs/` (`pdf.min.js` and `pdf.worker.min.js`) and served from this process.  
- **Offline after setup** — signature validation and PDF rendering do not require the public internet (no cdnjs or other remote script hosts). Setup still needs the network once to install Python packages.  
- **Sessions** expire after 30 minutes (in-memory decrypted copy for the local pdf.js preview)  
- **Validation** uses the **original uploaded bytes** (decrypt in memory only) so signature coverage stays intact  
- **Do not commit real e-Aadhaar PDFs** to git (see `.gitignore`)  

---

## Disclaimers

**Not legal advice.** Read and adapt for your use case.

- **No affiliation** — e-Aadhaar PDF Verifier is **not** affiliated with, endorsed by, or maintained by **UIDAI** (Unique Identification Authority of India), **Adobe**, **CCA India**, or any government body.  
- **Not UIDAI authentication** — this tool does **not** perform Aadhaar authentication, e-KYC, or identity verification against UIDAI services. It only checks the **digital signature** on a PDF file you provide.  
- **No official status** — a green tick in e-Aadhaar PDF Verifier means **cryptographic validation succeeded locally**; it does not replace official processes where a specific authority or format is required.  
- **Trademarks** — “Aadhaar”, “UIDAI”, “Adobe”, and “Acrobat” are trademarks of their respective owners. Use of those names here is **descriptive** (identifying the document type and comparison), not as branding or endorsement.  
- **Aadhaar logo** — do not use the UIDAI/Aadhaar logo in forks or derivatives without **written permission** from UIDAI.  
- **Your responsibility** — you are responsible for lawful handling of identity documents, passwords, and printed copies. Comply with applicable law (including India's IT Act and Aadhaar-related regulations) and organisational policies.  
- **Software warranty** — provided **“as is”** under the MIT License; authors are not liable for decisions made based on validation output.  

---

## Contributing

Issues and PRs welcome. Please **never** attach real e-Aadhaar PDFs, screenshots with Aadhaar numbers, or photos to issues or commits.

After `./setup.sh` (or `setup.bat`), run:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md). Latest: **v2.3.1**.

---

## License

[MIT](LICENSE)

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=danted4/eaadhaar-pdf-signature-verifier&type=Date)](https://star-history.com/#danted4/eaadhaar-pdf-signature-verifier&Date)
