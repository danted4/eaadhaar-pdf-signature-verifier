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
            with mock.patch.object(verify, "ROOT", self.root):
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
