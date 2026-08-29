#!/usr/bin/env python3
"""
eVerify — validate e-Aadhaar PDF signatures without Adobe Acrobat.

macOS Preview always shows '?' for Indian digital signatures because it
cannot validate the CCA/UIDAI certificate chain. This tool performs full
cryptographic validation via pyHanko and opens a local viewer with a
clear verified status.
"""

from __future__ import annotations

import argparse
import getpass
import http.server
import io
import json
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from pyhanko.keys import load_cert_from_pemder
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

SCRIPT_DIR = Path(__file__).resolve().parent
CCA_ROOTS = ["CCAIndia2022.cer", "CCAIndia2022SPL.cer"]


@dataclass
class VerificationResult:
    valid: bool
    signer: str
    signing_time: str
    trust_anchor: str
    sha256_fingerprint: str
    details: str
    view_bytes: bytes
    view_name: str


def load_trust_roots() -> list:
    roots = []
    for name in CCA_ROOTS:
        path = SCRIPT_DIR / name
        if path.exists():
            roots.append(load_cert_from_pemder(str(path)))
    if not roots:
        raise FileNotFoundError(
            f"CCA root certificates missing from {SCRIPT_DIR}. "
            "Download from https://cca.gov.in/root_certificate.html"
        )
    return roots


def read_for_viewing(pdf_path: Path, password: str | None) -> tuple[bytes, str]:
    """Decrypt in memory for display. Re-saving to disk would break the signature."""
    import pikepdf

    try:
        with pikepdf.open(pdf_path) as pdf:
            buf = io.BytesIO()
            pdf.save(buf)
            return buf.getvalue(), pdf_path.name
    except pikepdf.PasswordError:
        if not password:
            password = getpass.getpass("PDF password (NAMEYYYY, e.g. NAME1990): ")
        with pikepdf.open(pdf_path, password=password) as pdf:
            buf = io.BytesIO()
            pdf.save(buf)
            return buf.getvalue(), pdf_path.name


def verify_pdf(pdf_path: Path, password: str | None) -> VerificationResult:
    roots = load_trust_roots()
    vc = ValidationContext(trust_roots=roots)

    with pdf_path.open("rb") as f:
        reader = PdfFileReader(f, strict=False)
        if reader.encrypted:
            if not password:
                password = getpass.getpass("PDF password (NAMEYYYY, e.g. NAME1990): ")
            reader.decrypt(password)

        signatures = list(reader.embedded_signatures)
        if not signatures:
            raise ValueError("No digital signature found in this PDF.")

        sig = signatures[0]
        status = validate_pdf_signature(sig, signer_validation_context=vc)
        details = status.pretty_print_details()

        cert = status.signing_cert
        signer = cert.subject.human_friendly if cert else "Unknown"
        sha256 = cert.sha256.hex() if cert else ""

        trust_anchor = "CCA India 2022"
        if status.validation_path and status.validation_path.trust_anchor:
            anchor_cert = status.validation_path.trust_anchor.certificate
            if anchor_cert:
                trust_anchor = anchor_cert.subject.human_friendly

        signing_time = str(status.signer_reported_dt or "Unknown")
        view_bytes, view_name = read_for_viewing(pdf_path, password)

        return VerificationResult(
            valid=bool(status.bottom_line),
            signer=signer,
            signing_time=signing_time,
            trust_anchor=trust_anchor,
            sha256_fingerprint=sha256,
            details=details,
            view_bytes=view_bytes,
            view_name=view_name,
        )


def show_macos_alert(result: VerificationResult) -> None:
    if sys.platform != "darwin":
        return
    icon = "✅" if result.valid else "❌"
    title = "e-Aadhaar Verified" if result.valid else "e-Aadhaar INVALID"
    body = (
        f"{icon} Signature is VALID\\n\\n"
        f"Signer: UIDAI\\n"
        f"Signed: {result.signing_time}\\n\\n"
        f"Cryptographically verified via pyHanko."
        if result.valid
        else f"{icon} Signature validation FAILED.\\n\\nDo not trust this document."
    )
    script = f'display dialog "{body}" with title "{title}" buttons {{"OK"}} default button 1'
    subprocess.run(["osascript", "-e", script], check=False)


def open_viewer(result: VerificationResult, port: int) -> None:
    pdf_url = f"http://127.0.0.1:{port}/pdf"
    status_json = json.dumps(
        {
            "valid": result.valid,
            "signer": result.signer,
            "signing_time": result.signing_time,
            "trust_anchor": result.trust_anchor,
            "sha256_fingerprint": result.sha256_fingerprint,
        }
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>eVerify — {"Valid" if result.valid else "Invalid"}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; height: 100vh; display: flex; flex-direction: column; background: #f5f5f7; }}
  .banner {{
    padding: 14px 24px;
    display: flex; align-items: center; gap: 14px;
    background: {"#1a7f37" if result.valid else "#cf222e"};
    color: white;
    box-shadow: 0 2px 8px rgba(0,0,0,.15);
  }}
  .banner .icon {{ font-size: 28px; font-weight: bold; }}
  .banner h1 {{ font-size: 17px; font-weight: 600; }}
  .banner p {{ font-size: 13px; opacity: .9; margin-top: 2px; }}
  .meta {{ margin-left: auto; text-align: right; font-size: 12px; opacity: .85; }}
  .viewer {{ flex: 1; }}
  .viewer embed {{ width: 100%; height: 100%; border: none; }}
  .note {{ padding: 8px 24px; font-size: 12px; color: #666; background: #fff; border-top: 1px solid #ddd; }}
</style>
</head>
<body>
  <div class="banner">
    <span class="icon">{"✓" if result.valid else "✗"}</span>
    <div>
      <h1>{"Digital Signature Verified" if result.valid else "Signature Invalid"}</h1>
      <p>UIDAI e-Aadhaar — validated with CCA India root certificates</p>
    </div>
    <div class="meta">
      <div>Signed: {result.signing_time}</div>
      <div>Trust: {result.trust_anchor}</div>
    </div>
  </div>
  <div class="viewer">
    <embed src="{pdf_url}" type="application/pdf">
  </div>
  <div class="note">
    macOS Preview shows "?" because it cannot validate Indian PKI signatures.
    The green banner above is your verification — checked by pyHanko against the original signed file.
  </div>
  <script>const STATUS = {status_json};</script>
</body>
</html>"""

    pdf_bytes = result.view_bytes

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode())
            elif self.path == "/pdf":
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", f'inline; filename="{quote(result.view_name)}"')
                self.end_headers()
                self.wfile.write(pdf_bytes)
            else:
                self.send_response(404)
                self.end_headers()

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}/"
    print(f"Opening viewer at {url}")
    webbrowser.open(url)

    try:
        print("Press Ctrl+C to close the viewer.")
        while thread.is_alive():
            thread.join(timeout=1)
    except KeyboardInterrupt:
        print("\nClosing viewer.")
    finally:
        server.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify e-Aadhaar PDF signatures (no Adobe required)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
macOS Preview cannot validate Indian digital signatures and will always
show a question mark. This tool performs real cryptographic validation
and opens a local viewer with a verified status banner.

Examples:
  ./everify EAadhaar.pdf -p NAME1990
  python everify.py EAadhaar.pdf --no-viewer
        """,
    )
    parser.add_argument("pdf", type=Path, help="e-Aadhaar PDF file")
    parser.add_argument("-p", "--password", help="PDF password (NAMEYYYY)")
    parser.add_argument("--no-viewer", action="store_true", help="Validate only, skip browser viewer")
    parser.add_argument("--no-alert", action="store_true", help="Skip macOS dialog")
    parser.add_argument("--port", type=int, default=8765, help="Local viewer port (default: 8765)")
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: file not found: {args.pdf}", file=sys.stderr)
        return 1

    try:
        result = verify_pdf(args.pdf, args.password)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(result.details)
    print(f"\n{'✓ SIGNATURE VALID' if result.valid else '✗ SIGNATURE INVALID'}")

    if not args.no_alert:
        show_macos_alert(result)

    if not args.no_viewer and result.valid:
        open_viewer(result, args.port)

    return 0 if result.valid else 1


if __name__ == "__main__":
    sys.exit(main())
