"""Validate e-Aadhaar signatures and collect widget geometry for overlay."""

from __future__ import annotations

import io
import re
from pathlib import Path

import pikepdf
from pyhanko.keys import load_cert_from_pemder
from pyhanko.pdf_utils.crypt import AuthStatus
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

REPO_ROOT = Path(__file__).resolve().parent.parent
CERTS_DIR = REPO_ROOT / "certs"
CCA_ROOTS = ["CCAIndia2022.cer", "CCAIndia2022SPL.cer"]


def load_trust_roots():
    roots = []
    for name in CCA_ROOTS:
        path = CERTS_DIR / name
        if path.exists():
            roots.append(load_cert_from_pemder(str(path)))
    if not roots:
        raise FileNotFoundError("CCA root certificates missing from certs/")
    return roots


def _deref(obj):
    return obj.get_object() if hasattr(obj, "get_object") else obj


def _walk_pages(node, acc):
    node = _deref(node)
    kids = node.get("/Kids")
    if kids:
        for kid in _deref(kids):
            _walk_pages(kid, acc)
        return
    acc.append(node)


def _page_index(reader, field) -> int:
    target = _deref(field.get("/P"))
    pages = []
    _walk_pages(reader.root["/Pages"], pages)
    for i, page in enumerate(pages):
        if page is target:
            return i
        annots = page.get("/Annots")
        if not annots:
            continue
        for annot in _deref(annots):
            annot = _deref(annot)
            if annot is field:
                return i
    return 0


def _widget_annot(field):
    """The widget annotation of a signature field.

    Usually the field and its widget are one merged dictionary (e-Aadhaar is);
    otherwise the widget is a /Kids entry carrying /Rect, /P and /AP.
    """
    field = _deref(field)
    if "/Rect" in field:
        return field
    kids = field.get("/Kids")
    for kid in _deref(kids) if kids is not None else []:
        kid = _deref(kid)
        if "/Rect" in kid:
            return kid
    return field


def _rect(widget) -> list[float]:
    rect = widget.get("/Rect")
    if rect is None:  # no widget at all: treat as an invisible signature
        return [0.0, 0.0, 0.0, 0.0]
    return [float(x) for x in _deref(rect)]


def _inherited(node, key: str):
    """Look up an inheritable page attribute (e.g. /MediaBox) via /Parent."""
    node = _deref(node)
    for _ in range(64):  # guard against /Parent cycles in malformed files
        if node is None:
            return None
        if key in node:
            return _deref(node[key])
        parent = node.get("/Parent")
        node = _deref(parent) if parent is not None else None
    return None


# US Letter, the usual default when a malformed file has no MediaBox at all.
_DEFAULT_MEDIA_BOX = [0.0, 0.0, 612.0, 792.0]


def _media_box(reader, page_index: int) -> list[float]:
    pages = []
    _walk_pages(reader.root["/Pages"], pages)
    box = _inherited(pages[page_index], "/MediaBox")
    return [float(x) for x in box] if box is not None else list(_DEFAULT_MEDIA_BOX)


def _appearance(field) -> dict:
    """Read Acrobat n0–n4 signature layers so the viewer can swap ? → valid."""
    info = {
        "formWidth": 50.0,
        "formHeight": 30.0,
        "n1": {"a": 0.27, "b": 0.0, "c": 0.0, "d": 0.27, "e": 11.5, "f": 1.5, "bbox": [0, 0, 100, 100]},
        "n4": {"x": 2.0, "y": 23.3, "fontSize": 4.7, "height": 9.0},
    }
    try:
        ap = _deref(field["/AP"])
        n = _deref(ap["/N"])
        bbox = _deref(n.get("/BBox", [0, 0, 50, 30]))
        info["formWidth"] = float(bbox[2]) - float(bbox[0])
        info["formHeight"] = float(bbox[3]) - float(bbox[1])
        frm = _deref(_deref(_deref(n["/Resources"])["/XObject"])["/FRM"])
        data = frm.data.decode("latin1", "replace")
        match = re.search(
            r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+cm\s+/n1\s+Do",
            data,
        )
        if match:
            info["n1"].update(
                {
                    "a": float(match.group(1)),
                    "b": float(match.group(2)),
                    "c": float(match.group(3)),
                    "d": float(match.group(4)),
                    "e": float(match.group(5)),
                    "f": float(match.group(6)),
                }
            )
        xos = _deref(_deref(frm["/Resources"])["/XObject"])
        n1 = _deref(xos["/n1"])
        info["n1"]["bbox"] = [float(x) for x in _deref(n1["/BBox"])]
        n4 = _deref(xos["/n4"])
        n4_data = n4.data.decode("latin1", "replace")
        tm = re.search(r"1 0 0 1\s+([-\d.]+)\s+([-\d.]+)\s+Tm", n4_data)
        tf = re.search(r"/F1\s+([-\d.]+)\s+Tf", n4_data)
        if tm:
            info["n4"]["x"] = float(tm.group(1))
            info["n4"]["y"] = float(tm.group(2))
        if tf:
            info["n4"]["fontSize"] = float(tf.group(1))
        n4_box = _deref(n4["/BBox"])
        info["n4"]["height"] = float(n4_box[3]) - float(n4_box[1])
        n2 = _deref(xos["/n2"])
        n2_data = n2.data.decode("latin1", "replace")
        info["n2Lines"] = [
            line.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
            for line in re.findall(r"\(((?:\\.|[^\\)])*)\)Tj", n2_data)
        ]
        tms = re.findall(r"1 0 0 1\s+([-\d.]+)\s+([-\d.]+)\s+Tm", n2_data)
        tfs = re.findall(r"/F1\s+([-\d.]+)\s+Tf", n2_data)
        info["n2"] = {
            "x": float(tms[0][0]) if tms else 2.0,
            "ys": [float(t[1]) for t in tms],
            "fontSize": float(tfs[0]) if tfs else 3.4,
        }
    except Exception:
        pass
    return info


def decrypt_bytes(pdf_bytes: bytes, password: str | None) -> bytes:
    bio = io.BytesIO(pdf_bytes)
    try:
        pdf = pikepdf.open(bio)
    except pikepdf.PasswordError:
        if not password:
            raise ValueError("PDF is password-protected") from None
        try:
            pdf = pikepdf.open(io.BytesIO(pdf_bytes), password=password)
        except pikepdf.PasswordError:
            raise ValueError("Incorrect password") from None
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


def _widget_base(reader, field) -> dict:
    widget = _widget_annot(field)
    page_index = _page_index(reader, widget)
    return {
        "field": str(_deref(field.get("/T", "Signature"))),
        "pageIndex": page_index,
        "rect": _rect(widget),
        "mediaBox": _media_box(reader, page_index),
        "appearance": _appearance(widget),
    }


def preview_pdf_bytes(pdf_bytes: bytes, password: str | None) -> dict:
    """Decrypt for display and return widget geometry — no signature validation yet."""
    view_bytes = decrypt_bytes(pdf_bytes, password)
    reader = _open_reader(pdf_bytes, password)
    signatures = list(reader.embedded_signatures)
    if not signatures:
        raise ValueError("No digital signature found in this PDF")
    widgets = [_widget_base(reader, sig.sig_field) for sig in signatures]
    return {"widgets": widgets, "viewBytes": view_bytes}


def _open_reader(pdf_bytes: bytes, password: str | None) -> PdfFileReader:
    reader = PdfFileReader(io.BytesIO(pdf_bytes), strict=False)
    if reader.encrypted:
        if not password:
            raise ValueError("PDF is password-protected")
        if reader.decrypt(password).status == AuthStatus.FAILED:
            raise ValueError("Incorrect password")
    return reader


def _signer_cn(cert, subject: str) -> str:
    """The signer's common name, read from the certificate itself.

    Parsing the human-friendly subject string breaks on a CN containing a
    comma ("Doe, John"), so that is only the fallback.
    """
    if cert is not None:
        cn = cert.subject.native.get("common_name")
        if isinstance(cn, list):  # multi-valued RDN
            cn = ", ".join(str(part) for part in cn)
        if cn:
            return str(cn)
    return _cn_from_subject(subject)


def _cn_from_subject(subject: str) -> str:
    if "Common Name: " in subject:
        return subject.split("Common Name: ")[1].split(",")[0].strip()
    return subject.split(",")[0].strip() if subject else "Unknown"


NO_CHAIN_REASON = "certificate does not chain to a bundled CCA India root"
CHAIN_INVALID_REASON = "certificate chain could not be validated"
# Reasons that mean no trustworthy chain to a bundled root exists, so the
# report must not name a trust anchor.
_NO_ANCHOR_REASONS = {NO_CHAIN_REASON, CHAIN_INVALID_REASON}


def _local_date(dt) -> str:
    # The server runs on the user's own machine, so its local date matches the
    # local times the viewer shows (an e-Aadhaar expiring late UTC is next day IST).
    return dt.astimezone().date().isoformat()


def _validity_reason(status) -> str | None:
    """Date problem in the signer certificate or anywhere in its chain.

    pyHanko only reports an expired *signer* specifically (OUT_OF_BOUNDS_NO_POE);
    an expired sub-CA or a not-yet-valid certificate all come back as
    CERTIFICATE_CHAIN_GENERAL_FAILURE, so check the dates directly.
    """
    moment = status.validation_time
    if moment is None:
        return None
    cert = status.signing_cert
    if cert is not None:
        if cert.not_valid_after <= moment:
            return f"signer certificate expired ({_local_date(cert.not_valid_after)})"
        if cert.not_valid_before > moment:
            return "signer certificate not yet valid"
    path = status.validation_path
    if path is not None:
        for chain_cert in path.iter_certs(include_root=True):
            if chain_cert.not_valid_after <= moment:
                return f"a certificate in the chain expired ({_local_date(chain_cert.not_valid_after)})"
            if chain_cert.not_valid_before > moment:
                return "a certificate in the chain is not yet valid"
    return None


def _failure_reason(status) -> str | None:
    """One short, factual reason for an INVALID result (None when valid).

    Integrity problems win over trust problems: a modified file is reported as
    modified even if its certificate is also untrusted.
    """
    if status.bottom_line:
        return None
    if not status.intact:
        return "document changed after signing"
    if not status.valid:
        return "signature does not match the document"
    if getattr(status, "docmdp_ok", None) is False:
        return "file modified after signing"

    indic = status.trust_problem_indic
    name = getattr(indic, "name", "") if indic is not None else ""
    if name.startswith("REVOKED"):
        # REVOKED / REVOKED_NO_POE: the signer; REVOKED_CA_NO_POE: a CA above it.
        return "a certificate in the chain was revoked" if "_CA_" in name else "signer certificate revoked"
    if indic is not None or status.validation_path is None:
        if status.validation_path is None or name == "NO_CERTIFICATE_CHAIN_FOUND":
            return NO_CHAIN_REASON
        date_reason = _validity_reason(status)
        if date_reason:
            return date_reason
        if name == "CERTIFICATE_CHAIN_GENERAL_FAILURE":
            return CHAIN_INVALID_REASON
        return f"validation failed ({name.lower()})"

    ts = getattr(status, "timestamp_validity", None)
    if ts is not None and not (ts.valid and ts.intact and ts.trusted):
        return "signature timestamp is not valid"
    if getattr(status, "seed_value_ok", True) is False:
        return "signature field constraints not met"
    return "validation failed"


def _signature_report(status) -> dict:
    cert = status.signing_cert
    signer = cert.subject.human_friendly if cert else "Unknown"
    # Name a trust anchor only when a chain to it was actually established: no
    # path, or a path that failed the chain check, means "Not established".
    failure_reason = _failure_reason(status)
    trust_anchor = None
    if (
        failure_reason not in _NO_ANCHOR_REASONS
        and status.validation_path
        and status.validation_path.trust_anchor
    ):
        anchor = status.validation_path.trust_anchor.certificate
        if anchor:
            trust_anchor = anchor.subject.human_friendly

    coverage = getattr(status.coverage, "name", str(status.coverage or ""))
    return {
        "valid": bool(status.bottom_line),
        "signer": signer,
        "signerCn": _signer_cn(cert, signer),
        "signingTime": str(status.signer_reported_dt or "Unknown"),
        "validatedAt": str(status.validation_time or ""),
        "trustAnchor": trust_anchor,
        "certificateTrusted": bool(status.trusted),
        "integrityIntact": bool(status.intact),
        "coversEntireFile": coverage == "ENTIRE_FILE",
        "digestAlgorithm": status.md_algorithm or "",
        "signatureMechanism": status.pkcs7_signature_mechanism or "",
        "sha256": cert.sha256.hex() if cert else "",
        "sha1": cert.sha1.hex() if cert else "",
        "bottomLine": "VALID" if status.bottom_line else "INVALID",
        "failureReason": failure_reason,
    }


def _apply_signature_status(widget: dict, status) -> dict:
    report = _signature_report(status)
    widget.update(
        {
            "valid": report["valid"],
            "signer": report["signer"],
            "signerCn": report["signerCn"],
            "signingTime": report["signingTime"],
            "trustAnchor": report["trustAnchor"],
            "failureReason": report["failureReason"],
            "sha256": report["sha256"],
            "report": report,
        }
    )
    return widget


def validate_uploaded_bytes(pdf_bytes: bytes, password: str | None) -> dict:
    """Validate signatures on the original uploaded bytes (decrypt in-memory only)."""
    roots = load_trust_roots()
    vc = ValidationContext(trust_roots=roots)
    reader = _open_reader(pdf_bytes, password)

    signatures = list(reader.embedded_signatures)
    if not signatures:
        raise ValueError("No digital signature found in this PDF")

    widgets = []
    reports = []
    all_valid = True
    details = []

    for sig in signatures:
        status = validate_pdf_signature(sig, signer_validation_context=vc)
        valid = bool(status.bottom_line)
        all_valid = all_valid and valid
        details.append(status.pretty_print_details())

        widget = _widget_base(reader, sig.sig_field)
        _apply_signature_status(widget, status)
        widgets.append(widget)
        reports.append(widget["report"])

    return {
        "valid": all_valid,
        "details": "\n\n".join(details),
        "reports": reports,
        "widgets": widgets,
    }


def verify_pdf_bytes(pdf_bytes: bytes, password: str | None) -> dict:
    result = validate_uploaded_bytes(pdf_bytes, password)
    result["viewBytes"] = decrypt_bytes(pdf_bytes, password)
    return result
