"""In-process test CA and signed PDFs. No real Aadhaar, no network."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pikepdf
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign.signers import PdfSignatureMetadata, SimpleSigner, sign_pdf

PASSWORD = "secret"


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def make_ca_and_leaf(
    tmp: Path,
    *,
    leaf_not_before: datetime | None = None,
    leaf_not_after: datetime | None = None,
) -> tuple[Path, Path, Path]:
    """Write a test root CA and a signing leaf into `tmp`.

    Pass `leaf_not_before`/`leaf_not_after` to make an already-expired (or
    not-yet-valid) signer certificate; the CA stays valid either way.
    """
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(_name("Test Root CA"))
        .issuer_name(_name("Test Root CA"))
        .public_key(ca_key.public_key())
        .serial_number(1)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    leaf = (
        x509.CertificateBuilder()
        .subject_name(_name("Test Signer"))
        .issuer_name(ca_cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(2)
        .not_valid_before(leaf_not_before or now - timedelta(days=1))
        .not_valid_after(leaf_not_after or now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    ca_path = tmp / "CCAIndia2022.cer"
    leaf_cert = tmp / "leaf.crt"
    leaf_key_path = tmp / "leaf.key"
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    leaf_cert.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    leaf_key_path.write_bytes(
        leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return ca_path, leaf_cert, leaf_key_path


def _key_usage(*, ca: bool) -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=not ca,
        content_commitment=not ca,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=ca,
        crl_sign=ca,
        encipher_only=False,
        decipher_only=False,
    )


def _cert(subject, issuer, public_key, signing_key, serial, not_before, not_after, *, ca: bool):
    return (
        x509.CertificateBuilder()
        .subject_name(_name(subject))
        .issuer_name(_name(issuer))
        .public_key(public_key)
        .serial_number(serial)
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
        .add_extension(_key_usage(ca=ca), critical=True)
        .sign(signing_key, hashes.SHA256())
    )


def make_chain(
    tmp: Path,
    *,
    root_name: str = "Test Root CA",
    sub_validity: tuple[datetime, datetime] | None = None,
    leaf_validity: tuple[datetime, datetime] | None = None,
) -> tuple[Path, Path, Path, Path]:
    """Root -> sub-CA -> signer, like UIDAI's real chain (CCA -> sub-CA -> DS).

    Returns (root_path, sub_path, leaf_cert, leaf_key). The root is written as
    CCAIndia2022.cer so load_trust_roots() picks it up when CERTS_DIR is `tmp`.
    Each validity is (not_before, not_after); the default is valid now.
    """
    now = datetime.now(timezone.utc)
    default = (now - timedelta(days=1), now + timedelta(days=30))
    root_key, sub_key, leaf_key = (rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(3))
    root = _cert(root_name, root_name, root_key.public_key(), root_key, 1, now - timedelta(days=60), now + timedelta(days=60), ca=True)
    sub = _cert("Test Sub CA", root_name, sub_key.public_key(), root_key, 2, *(sub_validity or default), ca=True)
    leaf = _cert("Test Signer", "Test Sub CA", leaf_key.public_key(), sub_key, 3, *(leaf_validity or default), ca=False)
    paths = (tmp / "CCAIndia2022.cer", tmp / "sub.crt", tmp / "leaf.crt", tmp / "leaf.key")
    for path, cert in zip(paths[:3], (root, sub, leaf)):
        path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    paths[3].write_bytes(
        leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return paths


def sign_with_chain(raw: bytes, leaf_cert: Path, leaf_key: Path, chain: tuple[Path, ...]) -> bytes:
    signer = SimpleSigner.load(str(leaf_key), str(leaf_cert), ca_chain_files=tuple(str(c) for c in chain))
    writer = IncrementalPdfFileWriter(BytesIO(raw))
    out = sign_pdf(writer, PdfSignatureMetadata(field_name="Sig1"), signer)
    return out.getvalue() if hasattr(out, "getvalue") else out.read()


def blank_pdf_bytes() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    buf = BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def sign_pdf_bytes(raw: bytes, leaf_cert: Path, leaf_key: Path, ca_path: Path) -> bytes:
    signer = SimpleSigner.load(str(leaf_key), str(leaf_cert), ca_chain_files=(str(ca_path),))
    writer = IncrementalPdfFileWriter(BytesIO(raw))
    out = sign_pdf(writer, PdfSignatureMetadata(field_name="Sig1"), signer)
    return out.getvalue() if hasattr(out, "getvalue") else out.read()


def encrypt_pdf_bytes(raw: bytes, password: str = PASSWORD) -> bytes:
    buf = BytesIO()
    pikepdf.open(BytesIO(raw)).save(
        buf,
        encryption=pikepdf.Encryption(owner=password, user=password, R=6),
    )
    return buf.getvalue()


def tamper(raw: bytes) -> bytes:
    """Keep the PDF parseable but change signed page geometry."""
    match = re.search(rb"/MediaBox\s*\[[^\]]*\]", raw)
    if not match:
        raise RuntimeError("cannot locate MediaBox to tamper")
    old = match.group(0)
    new = old.replace(b"200", b"201", 1)
    if new == old:
        new = old[:-1] + b"1]"
    return raw[: match.start()] + new + raw[match.end() :]
