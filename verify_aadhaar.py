#!/usr/bin/env python3
"""Verify e-Aadhaar PDF digital signature using the same path as the viewer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from verify import validate_uploaded_bytes  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify e-Aadhaar PDF digital signature")
    parser.add_argument("pdf", type=Path, help="Path to e-Aadhaar PDF")
    parser.add_argument(
        "-p",
        "--password",
        help="PDF password (first 4 letters of name in CAPS + birth year, e.g. NAME1990)",
    )
    args = parser.parse_args(argv)

    if not args.pdf.exists():
        print(f"Error: File not found: {args.pdf}", file=sys.stderr)
        return 1

    try:
        result = validate_uploaded_bytes(args.pdf.read_bytes(), args.password)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(result["details"])
    print()
    print(f"Bottom line: {'VALID' if result['valid'] else 'INVALID'}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
