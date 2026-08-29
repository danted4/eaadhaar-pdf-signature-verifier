#!/usr/bin/env python3
"""Verify e-Aadhaar PDF digital signature using pyHanko."""

import argparse
import sys
from pathlib import Path

from pyhanko.keys import load_cert_from_pemder
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

SCRIPT_DIR = Path(__file__).resolve().parent
CCA_ROOTS = ["CCAIndia2022.cer", "CCAIndia2022SPL.cer"]


def verify(pdf_path: Path, password: str | None) -> bool:
    roots = []
    for cert_file in CCA_ROOTS:
        cert_path = SCRIPT_DIR / cert_file
        if cert_path.exists():
            roots.append(load_cert_from_pemder(str(cert_path)))

    if not roots:
        print("Error: CCA root certificates not found in script directory.", file=sys.stderr)
        return False

    vc = ValidationContext(trust_roots=roots)

    with pdf_path.open("rb") as f:
        reader = PdfFileReader(f, strict=False)
        if reader.encrypted:
            if not password:
                print("Error: PDF is password-protected. Provide --password.", file=sys.stderr)
                return False
            reader.decrypt(password)

        signatures = list(reader.embedded_signatures)
        if not signatures:
            print("Error: No embedded signatures found.", file=sys.stderr)
            return False

        all_valid = True
        for sig in signatures:
            status = validate_pdf_signature(sig, signer_validation_context=vc)
            print(status.pretty_print_details())
            if not status.bottom_line:
                all_valid = False

        return all_valid


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify e-Aadhaar PDF digital signature")
    parser.add_argument("pdf", type=Path, help="Path to e-Aadhaar PDF")
    parser.add_argument(
        "-p", "--password",
        help="PDF password (first 4 letters of name in CAPS + birth year, e.g. NAME1990)",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: File not found: {args.pdf}", file=sys.stderr)
        return 1

    valid = verify(args.pdf, args.password)
    print(f"\n{'✓ SIGNATURE VALID' if valid else '✗ SIGNATURE INVALID'}")
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
