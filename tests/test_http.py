"""HTTP handler tests on 127.0.0.1:0. No public internet."""

from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from support import REPO_ROOT

APP = str(REPO_ROOT / "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

import server  # noqa: E402
import verify  # noqa: E402

from pdf_fixtures import (  # noqa: E402
    blank_pdf_bytes,
    make_ca_and_leaf,
    sign_pdf_bytes,
)


def _multipart(pdf_bytes: bytes, password: str = "") -> tuple[bytes, str]:
    boundary = "----UnittestBoundary"
    parts = [
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="password"\r\n\r\n'
            f"{password}\r\n"
        ).encode(),
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="pdf"; filename="doc.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + pdf_bytes
        + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


# Written out by hand (not imported from server) so a loosened policy fails.
EXPECTED_CSP = {
    "default-src": {"'self'"},
    "script-src": {"'self'"},
    "worker-src": {"'self'"},
    "style-src": {"'self'"},
    "img-src": {"'self'", "data:"},
    "font-src": {"'self'"},
    "connect-src": {"'self'"},
    "object-src": {"'none'"},
    "base-uri": {"'none'"},
    "form-action": {"'none'"},
    "frame-ancestors": {"'none'"},
}


def _parse_csp(header: str | None) -> dict[str, set[str]]:
    policy: dict[str, set[str]] = {}
    for part in (header or "").split(";"):
        tokens = part.split()
        if tokens:
            policy[tokens[0].lower()] = set(tokens[1:])
    return policy


class ParseHelpersTests(unittest.TestCase):
    def test_content_length_rejects_negative(self) -> None:
        with self.assertRaises(ValueError) as cm:
            server.parse_content_length("-1")
        self.assertIn("Invalid Content-Length", str(cm.exception))

    def test_content_length_rejects_non_integer(self) -> None:
        with self.assertRaises(ValueError) as cm:
            server.parse_content_length("nope")
        self.assertIn("Invalid Content-Length", str(cm.exception))

    def test_content_length_rejects_over_max(self) -> None:
        with self.assertRaises(ValueError) as cm:
            server.parse_content_length(str(server.MAX_UPLOAD_BYTES + 1))
        self.assertIn("File too large", str(cm.exception))

    def test_content_length_accepts_zero_and_max(self) -> None:
        self.assertEqual(server.parse_content_length("0"), 0)
        self.assertEqual(
            server.parse_content_length(str(server.MAX_UPLOAD_BYTES)),
            server.MAX_UPLOAD_BYTES,
        )

    def test_parse_port_rejects_bad_values(self) -> None:
        with self.assertRaises(ValueError):
            server.parse_port("abc")
        with self.assertRaises(ValueError):
            server.parse_port("-1")
        with self.assertRaises(ValueError):
            server.parse_port("70000")
        self.assertEqual(server.parse_port("8765"), 8765)
        self.assertEqual(server.parse_port("0"), 0)

    def test_bind_ephemeral_port(self) -> None:
        httpd = server.bind_server(0)
        try:
            host, port = httpd.server_address
            self.assertEqual(host, "127.0.0.1")
            self.assertGreater(port, 0)
        finally:
            httpd.server_close()

    def test_bind_oserror_message(self) -> None:
        class Boom(ThreadingHTTPServer):
            def __init__(self, *args, **kwargs):
                raise OSError("Address already in use")

        with self.assertRaises(OSError) as cm:
            server.bind_server(8765, server_class=Boom)
        self.assertIn("127.0.0.1:8765", str(cm.exception))

    def test_main_bad_port_exits_1(self) -> None:
        self.assertEqual(server.main(["not-a-port"]), 1)
        self.assertEqual(server.main(["99999"]), 1)

    def test_main_bind_failure_exits_1(self) -> None:
        def boom(port, server_class=ThreadingHTTPServer):
            raise OSError(f"Could not listen on 127.0.0.1:{port}: in use")

        with mock.patch.object(server, "bind_server", boom):
            self.assertEqual(server.main(["8765"]), 1)


class HttpServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.ca, cls.leaf_cert, cls.leaf_key = make_ca_and_leaf(cls.root)
        cls.signed = sign_pdf_bytes(blank_pdf_bytes(), cls.leaf_cert, cls.leaf_key, cls.ca)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls._tmp.cleanup()

    def setUp(self) -> None:
        with server.SESSIONS_LOCK:
            server.SESSIONS.clear()

    def _conn(self) -> http.client.HTTPConnection:
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)

    def test_preview_size_limit_without_reading_body(self) -> None:
        conn = self._conn()
        try:
            conn.putrequest("POST", "/api/preview")
            conn.putheader("Content-Type", "multipart/form-data; boundary=x")
            conn.putheader("Content-Length", str(server.MAX_UPLOAD_BYTES + 1))
            conn.endheaders()
            resp = conn.getresponse()
            body = json.loads(resp.read())
        finally:
            conn.close()
        self.assertEqual(resp.status, 413)
        self.assertIn("too large", body["error"].lower())

    def test_negative_content_length(self) -> None:
        conn = self._conn()
        try:
            conn.putrequest("POST", "/api/preview")
            conn.putheader("Content-Type", "multipart/form-data; boundary=x")
            conn.putheader("Content-Length", "-1")
            conn.endheaders()
            resp = conn.getresponse()
            body = json.loads(resp.read())
        finally:
            conn.close()
        self.assertEqual(resp.status, 400)
        self.assertIn("Invalid Content-Length", body["error"])

    def test_validate_json_size_limit(self) -> None:
        conn = self._conn()
        try:
            conn.putrequest("POST", "/api/validate")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", str(server.MAX_JSON_BYTES + 1))
            conn.endheaders()
            resp = conn.getresponse()
            body = json.loads(resp.read())
        finally:
            conn.close()
        self.assertEqual(resp.status, 413)

    def test_missing_session(self) -> None:
        conn = self._conn()
        try:
            conn.request("GET", "/api/pdf/not-a-session")
            resp = conn.getresponse()
            raw = resp.read()
        finally:
            conn.close()
        self.assertEqual(resp.status, 404)
        self.assertIn(b"expired", raw)

    def _post_validate(self, raw: bytes) -> tuple[int, dict]:
        conn = self._conn()
        try:
            conn.request("POST", "/api/validate", body=raw, headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            conn.close()

    def test_validate_rejects_malformed_bodies_with_400(self) -> None:
        # Each of these used to raise inside the handler and drop the connection,
        # which the viewer would misreport as "Cannot reach the server".
        for raw in (b"[]", b'"x"', b"5", b'{"sessionId": 5}', b'{"sessionId": null}', b"\xff\xfe"):
            with self.subTest(raw=raw):
                status, body = self._post_validate(raw)
                self.assertEqual(status, 400)
                self.assertIn("error", body)

    def test_session_expired_message_is_actionable(self) -> None:
        status, body = self._post_validate(json.dumps({"sessionId": "gone"}).encode())
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], 'Session expired. Click "Open another" and open the PDF again.')
        self.assertNotIn("\u2014", body["error"])

    def _status_with_host(self, method: str, path: str, host: str | None) -> int:
        conn = self._conn()
        try:
            conn.putrequest(method, path, skip_host=host is None or host != "default")
            if host not in (None, "default"):
                conn.putheader("Host", host)
            conn.putheader("Content-Length", "0")
            conn.endheaders()
            resp = conn.getresponse()
            resp.read()
            return resp.status
        finally:
            conn.close()

    def test_foreign_host_is_rejected(self) -> None:
        # DNS rebinding: a page on evil.example resolving to 127.0.0.1 sends its own Host.
        for method, path in (("GET", "/"), ("GET", "/static/viewer.js"), ("POST", "/api/validate")):
            for host in ("evil.example", f"evil.example:{self.port}", "127.0.0.1:1", "", None):
                with self.subTest(method=method, path=path, host=host):
                    self.assertEqual(self._status_with_host(method, path, host), 403)

    def test_local_hosts_are_allowed(self) -> None:
        for host in (f"127.0.0.1:{self.port}", f"localhost:{self.port}", f"LOCALHOST:{self.port}", "default"):
            with self.subTest(host=host):
                self.assertEqual(self._status_with_host("GET", "/", host), 200)

    def test_static_path_traversal(self) -> None:
        conn = self._conn()
        try:
            conn.request("GET", "/static/../server.py")
            resp = conn.getresponse()
            resp.read()
        finally:
            conn.close()
        self.assertEqual(resp.status, 404)

    def test_vendored_pdfjs_is_served(self) -> None:
        conn = self._conn()
        try:
            conn.request("GET", "/static/pdfjs/pdf.min.js")
            resp = conn.getresponse()
            data = resp.read()
        finally:
            conn.close()
        self.assertEqual(resp.status, 200)
        self.assertGreater(len(data), 1000)

    def test_security_headers_on_every_response(self) -> None:
        # (method, path, body): HTML, static JS, the pdf.js worker (its own
        # response CSP governs eval inside the worker), a 404, a JSON error,
        # and a stdlib send_error() page (501 for an unsupported method).
        requests = [
            ("GET", "/", None),
            ("GET", "/static/pdfjs/pdf.min.js", None),
            ("GET", "/static/pdfjs/pdf.worker.min.js", None),
            ("GET", "/api/pdf/not-a-session", None),
            ("POST", "/api/validate", json.dumps({"sessionId": "nope"})),
            ("PUT", "/", ""),
        ]
        for method, path, body in requests:
            conn = self._conn()
            try:
                conn.request(method, path, body=body, headers={"Content-Type": "application/json"})
                resp = conn.getresponse()
                resp.read()
            finally:
                conn.close()
            with self.subTest(method=method, path=path, status=resp.status):
                # Whole-policy comparison: any added source (*, https:, blob:,
                # 'unsafe-*') or loosened directive fails here.
                self.assertEqual(_parse_csp(resp.getheader("Content-Security-Policy")), EXPECTED_CSP)
                self.assertEqual(resp.getheader("X-Content-Type-Options"), "nosniff")

    def test_preview_and_validate_with_test_root(self) -> None:
        body, ctype = _multipart(self.signed)
        conn = self._conn()
        try:
            conn.request("POST", "/api/preview", body=body, headers={"Content-Type": ctype})
            resp = conn.getresponse()
            payload = json.loads(resp.read())
        finally:
            conn.close()
        self.assertEqual(resp.status, 200, payload)
        sid = payload["sessionId"]
        conn = self._conn()
        try:
            with mock.patch.object(verify, "CERTS_DIR", self.root):
                conn.request(
                    "POST",
                    "/api/validate",
                    body=json.dumps({"sessionId": sid}),
                    headers={"Content-Type": "application/json"},
                )
                vresp = conn.getresponse()
                vbody = json.loads(vresp.read())
        finally:
            conn.close()
        self.assertEqual(vresp.status, 200, vbody)
        self.assertTrue(vbody["valid"])


if __name__ == "__main__":
    unittest.main()
