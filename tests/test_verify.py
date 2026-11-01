"""Core validation tests using an in-process CA (no real Aadhaar, no network)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import REPO_ROOT

APP = str(REPO_ROOT / "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

import verify  # noqa: E402

from pdf_fixtures import (  # noqa: E402
    PASSWORD,
    blank_pdf_bytes,
    encrypt_pdf_bytes,
    make_ca_and_leaf,
    sign_pdf_bytes,
    tamper,
)


class VerifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.ca, cls.leaf_cert, cls.leaf_key = make_ca_and_leaf(cls.root)
        cls.unsigned = blank_pdf_bytes()
        cls.signed = sign_pdf_bytes(cls.unsigned, cls.leaf_cert, cls.leaf_key, cls.ca)
        cls.encrypted = encrypt_pdf_bytes(cls.signed, PASSWORD)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_valid_signature_with_test_root(self) -> None:
        with mock.patch.object(verify, "ROOT", self.root):
            result = verify.validate_uploaded_bytes(self.signed, None)
        self.assertTrue(result["valid"])
        self.assertTrue(result["reports"][0]["valid"])

    def test_tampered_bytes_are_invalid(self) -> None:
        with mock.patch.object(verify, "ROOT", self.root):
            result = verify.validate_uploaded_bytes(tamper(self.signed), None)
        self.assertFalse(result["valid"])

    def test_missing_password(self) -> None:
        with self.assertRaises(ValueError) as cm:
            verify.preview_pdf_bytes(self.encrypted, None)
        self.assertIn("password-protected", str(cm.exception))

    def test_wrong_password(self) -> None:
        with self.assertRaises(ValueError) as cm:
            verify.preview_pdf_bytes(self.encrypted, "nope")
        self.assertIn("Incorrect password", str(cm.exception))

    def test_no_signature(self) -> None:
        with mock.patch.object(verify, "ROOT", self.root):
            with self.assertRaises(ValueError) as cm:
                verify.validate_uploaded_bytes(self.unsigned, None)
        self.assertIn("No digital signature", str(cm.exception))

    def test_missing_cca_files(self) -> None:
        empty = self.root / "empty"
        empty.mkdir(exist_ok=True)
        with mock.patch.object(verify, "ROOT", empty):
            with self.assertRaises(FileNotFoundError):
                verify.load_trust_roots()


if __name__ == "__main__":
    unittest.main()
