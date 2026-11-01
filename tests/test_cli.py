"""CLI uses app.verify; ValueError becomes stderr + exit 1."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
APP = str(REPO_ROOT / "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

import verify  # noqa: E402
import verify_aadhaar  # noqa: E402

from pdf_fixtures import blank_pdf_bytes, make_ca_and_leaf, sign_pdf_bytes  # noqa: E402


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.ca, cls.leaf_cert, cls.leaf_key = make_ca_and_leaf(cls.root)
        cls.signed_path = cls.root / "signed.bin"
        cls.signed_path.write_bytes(
            sign_pdf_bytes(blank_pdf_bytes(), cls.leaf_cert, cls.leaf_key, cls.ca)
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_cli_valid_bottom_line(self) -> None:
        stdout = io.StringIO()
        with mock.patch.object(verify, "CERTS_DIR", self.root), mock.patch("sys.stdout", stdout):
            code = verify_aadhaar.main([str(self.signed_path)])
        self.assertEqual(code, 0)
        self.assertIn("Bottom line: VALID", stdout.getvalue())

    def test_cli_missing_file(self) -> None:
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            code = verify_aadhaar.main([str(self.root / "missing.bin")])
        self.assertEqual(code, 1)
        self.assertIn("File not found", stderr.getvalue())

    def test_cli_maps_valueerror(self) -> None:
        unsigned = self.root / "unsigned.bin"
        unsigned.write_bytes(blank_pdf_bytes())
        stderr = io.StringIO()
        with mock.patch.object(verify, "CERTS_DIR", self.root), mock.patch("sys.stderr", stderr):
            code = verify_aadhaar.main([str(unsigned)])
        self.assertEqual(code, 1)
        self.assertIn("No digital signature", stderr.getvalue())

    def test_cli_does_not_reimplement_validation(self) -> None:
        source = (REPO_ROOT / "verify_aadhaar.py").read_text(encoding="utf-8")
        self.assertIn("validate_uploaded_bytes", source)
        self.assertNotIn("validate_pdf_signature", source)
        self.assertNotIn("reader.decrypt(", source)


if __name__ == "__main__":
    unittest.main()
