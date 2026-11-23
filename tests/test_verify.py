"""Core validation tests using an in-process CA (no real Aadhaar, no network)."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
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
    make_chain,
    sign_pdf_bytes,
    sign_with_chain,
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
        # Same subject name, different key: a path is built but cannot validate.
        self.assertEqual(report["failureReason"], "certificate chain could not be validated")
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
            f"signer certificate expired ({not_after.astimezone().date().isoformat()})",
        )
        self.assertIn("Test Root CA", report["trustAnchor"])

    def _chain_report(self, label: str, **chain_kwargs) -> dict:
        d = self.root / label
        d.mkdir(exist_ok=True)
        root, sub, leaf, key = make_chain(d, **chain_kwargs)
        signed = sign_with_chain(blank_pdf_bytes(), leaf, key, (sub, root))
        with mock.patch.object(verify, "CERTS_DIR", d):
            result = verify.validate_uploaded_bytes(signed, None)
        report = result["reports"][0]
        self.assertTrue(report["integrityIntact"], label)
        return report

    def test_chain_all_valid(self) -> None:
        report = self._chain_report("chain-ok")
        self.assertTrue(report["valid"])
        self.assertIsNone(report["failureReason"])

    def test_expired_sub_ca_is_not_reported_as_no_chain(self) -> None:
        now = datetime.now(timezone.utc)
        sub_end = now - timedelta(days=3)
        report = self._chain_report("sub-expired", sub_validity=(now - timedelta(days=40), sub_end))
        self.assertEqual(report["failureReason"], f"a certificate in the chain expired ({sub_end.astimezone().date().isoformat()})")
        self.assertIn("Test Root CA", report["trustAnchor"])

    def test_signer_expiry_wins_over_expired_sub_ca(self) -> None:
        now = datetime.now(timezone.utc)
        leaf_end = now - timedelta(days=2)
        report = self._chain_report(
            "both-expired",
            sub_validity=(now - timedelta(days=40), now - timedelta(days=3)),
            leaf_validity=(now - timedelta(days=30), leaf_end),
        )
        self.assertEqual(report["failureReason"], f"signer certificate expired ({leaf_end.astimezone().date().isoformat()})")

    def test_not_yet_valid_signer(self) -> None:
        now = datetime.now(timezone.utc)
        report = self._chain_report("future", leaf_validity=(now + timedelta(days=2), now + timedelta(days=30)))
        self.assertEqual(report["failureReason"], "signer certificate not yet valid")

    def test_root_with_different_name_is_no_chain(self) -> None:
        # Signed under "Test Root CA"; the only bundled root has another name.
        d = self.root / "other-name"
        d.mkdir(exist_ok=True)
        root, sub, leaf, key = make_chain(d)
        signed = sign_with_chain(blank_pdf_bytes(), leaf, key, (sub, root))
        trust = self.root / "other-name-trust"
        trust.mkdir(exist_ok=True)
        make_chain(trust, root_name="Some Other Root")
        with mock.patch.object(verify, "CERTS_DIR", trust):
            report = verify.validate_uploaded_bytes(signed, None)["reports"][0]
        self.assertEqual(report["failureReason"], "certificate does not chain to a bundled CCA India root")
        self.assertIsNone(report["trustAnchor"])

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


def _stub(**overrides):
    base = dict(
        bottom_line=False, intact=True, valid=True, docmdp_ok=True, trust_problem_indic=None,
        validation_path=object(), validation_time=None, signing_cert=None,
        timestamp_validity=None, seed_value_ok=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class FailureReasonPrecedenceTests(unittest.TestCase):
    """Pin the order of _failure_reason with stub statuses (pure function)."""

    def test_table(self) -> None:
        indic = lambda name: SimpleNamespace(name=name)  # noqa: E731
        bad_ts = SimpleNamespace(valid=False, intact=True, trusted=True)
        cases = [
            (_stub(bottom_line=True), None),
            (_stub(intact=False, valid=False, trust_problem_indic=indic("NO_CERTIFICATE_CHAIN_FOUND")), "document changed after signing"),
            (_stub(valid=False, docmdp_ok=False), "signature does not match the document"),
            (_stub(docmdp_ok=False, trust_problem_indic=indic("NO_CERTIFICATE_CHAIN_FOUND")), "file modified after signing"),
            (_stub(trust_problem_indic=indic("REVOKED_NO_POE")), "signer certificate revoked"),
            (_stub(trust_problem_indic=indic("REVOKED_CA_NO_POE")), "a certificate in the chain was revoked"),
            (_stub(trust_problem_indic=indic("NO_CERTIFICATE_CHAIN_FOUND")), "certificate does not chain to a bundled CCA India root"),
            (_stub(validation_path=None), "certificate does not chain to a bundled CCA India root"),
            (_stub(trust_problem_indic=indic("CERTIFICATE_CHAIN_GENERAL_FAILURE")), "certificate chain could not be validated"),
            (_stub(trust_problem_indic=indic("CRYPTO_CONSTRAINTS_FAILURE")), "validation failed (crypto_constraints_failure)"),
            (_stub(timestamp_validity=bad_ts), "signature timestamp is not valid"),
            (_stub(seed_value_ok=False), "signature field constraints not met"),
            (_stub(), "validation failed"),
        ]
        for status, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(verify._failure_reason(status), expected)


if __name__ == "__main__":
    unittest.main()
