#!/usr/bin/env python3
"""Local e-Aadhaar PDF signature verifier: validate, overlay validity mark, preview + print."""

from __future__ import annotations

import json
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
PROTO = ROOT.parent / "prototype"
sys.path.insert(0, str(ROOT))

from verify import preview_pdf_bytes, validate_uploaded_bytes, verify_pdf_bytes  # noqa: E402

SESSIONS: dict[str, dict] = {}
SESSIONS_LOCK = threading.Lock()
TTL_SECONDS = 30 * 60
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_JSON_BYTES = 64 * 1024

# Single source of the release number shown in the UI (filled into index.html
# when served). Bump it with README's "Current release" line and CHANGELOG;
# tests/test_http.py fails if it drifts from the README.
APP_VERSION = "2.3.6"

# No 'unsafe-eval': a crafted PDF must not be able to run script on this page
# (pdf.js CVE-2024-4367) and fake the green tick. No 'unsafe-inline' either:
# the print iframe uses CSSOM and /static/print-frame.css. pdf.js loads fonts
# with the FontFace API (binary data, not governed by font-src); its legacy
# @font-face fallback needs a script-made <style>, which style-src blocks anyway.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "worker-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ]
)


def parse_content_length(header_value: str | None, max_bytes: int = MAX_UPLOAD_BYTES) -> int:
    raw = "0" if header_value is None or str(header_value).strip() == "" else str(header_value).strip()
    try:
        length = int(raw)
    except (TypeError, ValueError):
        raise ValueError("Invalid Content-Length") from None
    if length < 0:
        raise ValueError("Invalid Content-Length")
    if length > max_bytes:
        raise ValueError("File too large")
    return length


def parse_port(value: str) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid port: {value}") from None
    if port < 0 or port > 65535:
        raise ValueError(f"Invalid port: {value}")
    return port


def bind_server(port: int, server_class=ThreadingHTTPServer):
    try:
        return server_class(("127.0.0.1", port), Handler)
    except OSError as exc:
        raise OSError(f"Could not listen on 127.0.0.1:{port}: {exc}") from exc


def _purge_unlocked():
    now = time.time()
    dead = [k for k, v in SESSIONS.items() if now - v["created"] > TTL_SECONDS]
    for k in dead:
        SESSIONS.pop(k, None)


def _purge():
    with SESSIONS_LOCK:
        _purge_unlocked()


class Handler(BaseHTTPRequestHandler):
    def end_headers(self):
        # Every response, including stdlib send_error() pages, gets these.
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _host_allowed(self) -> bool:
        """Only answer requests addressed to this machine by name.

        A page on another site can point its own hostname at 127.0.0.1 (DNS
        rebinding); its requests then carry that hostname in Host. The hostname
        is what matters, so any port is accepted: SSH tunnels and port
        forwarding reach us on a different port than the one we bound.
        """
        host = (self.headers.get("Host") or "").strip().lower()
        name, sep, port = host.rpartition(":")
        if not sep:
            name, port = host, ""
        return name in ("127.0.0.1", "localhost") and (port == "" or port.isdigit())

    def _reject_foreign_host(self) -> bool:
        if self._host_allowed():
            return False
        self._send(403, b"Forbidden host", "text/plain")
        return True

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict):
        self._send(code, json.dumps(payload).encode(), "application/json")

    def do_GET(self):
        if self._reject_foreign_host():
            return
        _purge()
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            html = (STATIC / "index.html").read_bytes().replace(b"__APP_VERSION__", APP_VERSION.encode())
            self._send(200, html, "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            name = path[len("/static/") :]
            file = STATIC / name
            if not file.resolve().is_relative_to(STATIC.resolve()) or not file.is_file():
                self._send(404, b"not found", "text/plain")
                return
            types = {".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml"}
            self._send(200, file.read_bytes(), types.get(file.suffix, "application/octet-stream"))
            return
        if path.startswith("/prototype/"):
            name = path[len("/prototype/") :]
            file = PROTO / name
            if not file.resolve().is_relative_to(PROTO.resolve()) or not file.is_file():
                self._send(404, b"not found", "text/plain")
                return
            types = {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript",
                ".css": "text/css",
                ".png": "image/png",
            }
            self._send(200, file.read_bytes(), types.get(file.suffix, "application/octet-stream"))
            return
        if path.startswith("/api/pdf/"):
            sid = path.rsplit("/", 1)[-1]
            with SESSIONS_LOCK:
                _purge_unlocked()
                session = SESSIONS.get(sid)
                pdf = session["pdf"] if session else None
            if not session:
                self._send(404, b"expired", "text/plain")
                return
            self._send(200, pdf, "application/pdf")
            return

        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self._reject_foreign_host():
            return
        _purge()
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/preview":
            self._handle_preview()
            return
        if path == "/api/validate":
            self._handle_validate()
            return
        if path == "/api/verify":
            self._handle_verify()
            return
        self._send(404, b"not found", "text/plain")

    def _read_multipart_pdf(self) -> tuple[str, bytes]:
        length = parse_content_length(self.headers.get("Content-Length"), MAX_UPLOAD_BYTES)
        content_type = self.headers.get("Content-Type", "")
        body = self.rfile.read(length)
        password, pdf_bytes = _parse_multipart(content_type, body)
        if not pdf_bytes:
            raise ValueError("No PDF uploaded")
        return password, pdf_bytes

    def _handle_preview(self):
        try:
            password, pdf_bytes = self._read_multipart_pdf()
            result = preview_pdf_bytes(pdf_bytes, password or None)
        except ValueError as exc:
            code = 413 if str(exc) == "File too large" else 400
            self._json(code, {"error": str(exc)})
            return
        except Exception as exc:
            self._json(400, {"error": str(exc)})
            return

        sid = uuid.uuid4().hex
        with SESSIONS_LOCK:
            _purge_unlocked()
            SESSIONS[sid] = {
                "pdf": result["viewBytes"],
                "original": pdf_bytes,
                "password": password or "",
                "created": time.time(),
            }
        self._json(
            200,
            {
                "sessionId": sid,
                "widgets": result["widgets"],
            },
        )

    def _handle_validate(self):
        try:
            length = parse_content_length(self.headers.get("Content-Length"), MAX_JSON_BYTES)
        except ValueError as exc:
            code = 413 if str(exc) == "File too large" else 400
            self._json(code, {"error": str(exc)})
            return
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, RecursionError):  # bad JSON, non-UTF-8, absurd nesting
            self._json(400, {"error": "Invalid JSON"})
            return
        sid = payload.get("sessionId", "") if isinstance(payload, dict) else None
        if not isinstance(sid, str):
            self._json(400, {"error": "Invalid request"})
            return
        with SESSIONS_LOCK:
            _purge_unlocked()
            session = SESSIONS.get(sid)
            original = session["original"] if session else None
            password = (session.get("password") or None) if session else None
        if not session:
            self._json(404, {"error": 'Session expired. Click "Open another" and open the PDF again.'})
            return
        try:
            result = validate_uploaded_bytes(original, password)
        except Exception as exc:
            self._json(400, {"error": str(exc)})
            return
        with SESSIONS_LOCK:
            if sid in SESSIONS:
                SESSIONS[sid]["validated"] = True
        self._json(
            200,
            {
                "sessionId": sid,
                "valid": result["valid"],
                "details": result["details"],
                "reports": result.get("reports", []),
                "widgets": result["widgets"],
            },
        )

    def _handle_verify(self):
        try:
            password, pdf_bytes = self._read_multipart_pdf()
            result = verify_pdf_bytes(pdf_bytes, password or None)
        except ValueError as exc:
            code = 413 if str(exc) == "File too large" else 400
            self._json(code, {"error": str(exc)})
            return
        except Exception as exc:
            self._json(400, {"error": str(exc)})
            return

        sid = uuid.uuid4().hex
        with SESSIONS_LOCK:
            _purge_unlocked()
            SESSIONS[sid] = {
                "pdf": result["viewBytes"],
                "original": pdf_bytes,
                "password": password or "",
                "created": time.time(),
                "validated": True,
            }
        self._json(
            200,
            {
                "sessionId": sid,
                "valid": result["valid"],
                "details": result["details"],
                "reports": result.get("reports", []),
                "widgets": result["widgets"],
            },
        )


def _parse_multipart(content_type: str, body: bytes) -> tuple[str, bytes]:
    if "multipart/form-data" not in content_type:
        return "", b""
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("boundary="):
            boundary = part.split("=", 1)[1].strip().strip('"')
    if not boundary:
        return "", b""

    password = ""
    pdf_bytes = b""
    marker = b"--" + boundary.encode()
    chunks = body.split(marker)
    for chunk in chunks:
        chunk = chunk.lstrip(b"\r\n")
        if not chunk or chunk.startswith(b"--"):
            continue
        header_blob, _, data = chunk.partition(b"\r\n\r\n")
        # MIME parts end with CRLF before the next boundary. Do not rstrip —
        # that would also eat trailing newlines that belong to the PDF.
        if data.endswith(b"\r\n"):
            data = data[:-2]
        elif data.endswith(b"\n"):
            data = data[:-1]
        headers = header_blob.decode("utf-8", "replace")
        if 'name="password"' in headers:
            password = data.decode("utf-8", "replace")
        elif 'name="pdf"' in headers:
            pdf_bytes = data
    return password, pdf_bytes


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    port = 8765
    if argv:
        try:
            port = parse_port(argv[0])
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    try:
        httpd = bind_server(port)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    bound_port = httpd.server_address[1]
    url = f"http://127.0.0.1:{bound_port}/"
    print(f"e-Aadhaar PDF Signature Verifier at {url}")
    print("Original PDF is never modified. Ctrl+C to quit.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
