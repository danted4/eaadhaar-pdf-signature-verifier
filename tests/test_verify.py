"""Core validation tests using an in-process CA (no real Aadhaar, no network)."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
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
        with mock.patch.object(verify, "CERTS_DIR", self.root):
            result = verify.validate_uploaded_bytes(self.signed, None)
        self.assertTrue(result["valid"])
        self.assertTrue(result["reports"][0]["valid"])

    def test_tampered_bytes_are_invalid(self) -> None:
        with mock.patch.object(verify, "CERTS_DIR", self.root):
            result = verify.validate_uploaded_bytes(tamper(self.signed), None)
        self.assertFalse(result["valid"])

    def test_valid_has_no_failure_reason_and_names_anchor(self) -> None:
        with mock.patch.object(verify, "CERTS_DIR", self.root):
            report = verify.validate_uploaded_bytes(self.signed, None)["reports"][0]
        self.assertIsNone(report["failureReason"])
        self.assertIn("Test Root CA", report["trustAnchor"])

    def test_tampered_reason(self) -> None:
        with mock.patch.object(verify, "CERTS_DIR", self.root):
            result = verify.validate_uploaded_bytes(tamper(self.signed), None)
        self.assertEqual(result["reports"][0]["failureReason"], "document changed after signing")
        self.assertEqual(result["widgets"][0]["failureReason"], "document changed after signing")

    def test_untrusted_chain_reason_and_no_anchor(self) -> None:
        # Validate against a different root: the signer chains to nothing bundled.
        other = self.root / "other-root"
        other.mkdir(exist_ok=True)
        make_ca_and_leaf(other)
        with mock.patch.object(verify, "CERTS_DIR", other):
            result = verify.validate_uploaded_bytes(self.signed, None)
        report = result["reports"][0]
        self.assertFalse(result["valid"])
        self.assertTrue(report["integrityIntact"])
        self.assertEqual(report["failureReason"], "certificate does not chain to a bundled CCA India root")
        self.assertIsNone(report["trustAnchor"])

    def test_expired_signer_reason_has_date(self) -> None:
        now = datetime.now(timezone.utc)
        expired_dir = self.root / "expired"
        expired_dir.mkdir(exist_ok=True)
        not_after = now - timedelta(days=2)
        ca, leaf_cert, leaf_key = make_ca_and_leaf(
            expired_dir, leaf_not_before=now - timedelta(days=30), leaf_not_after=not_after
        )
        signed = sign_pdf_bytes(blank_pdf_bytes(), leaf_cert, leaf_key, ca)
        with mock.patch.object(verify, "CERTS_DIR", expired_dir):
            result = verify.validate_uploaded_bytes(signed, None)
        report = result["reports"][0]
        self.assertFalse(result["valid"])
        self.assertTrue(report["integrityIntact"])
        self.assertEqual(
            report["failureReason"],
            f"signer certificate expired ({not_after.date().isoformat()})",
        )

    def test_missing_password(self) -> None:
        with self.assertRaises(ValueError) as cm:
            verify.preview_pdf_bytes(self.encrypted, None)
        self.assertIn("password-protected", str(cm.exception))

    def test_wrong_password(self) -> None:
        with self.assertRaises(ValueError) as cm:
            verify.preview_pdf_bytes(self.encrypted, "nope")
        self.assertIn("Incorrect password", str(cm.exception))

    def test_no_signature(self) -> None:
        with mock.patch.object(verify, "CERTS_DIR", self.root):
            with self.assertRaises(ValueError) as cm:
                verify.validate_uploaded_bytes(self.unsigned, None)
        self.assertIn("No digital signature", str(cm.exception))

    def test_missing_cca_files(self) -> None:
        empty = self.root / "empty"
        empty.mkdir(exist_ok=True)
        with mock.patch.object(verify, "CERTS_DIR", empty):
            with self.assertRaises(FileNotFoundError):
                verify.load_trust_roots()


if __name__ == "__main__":
    unittest.main()
