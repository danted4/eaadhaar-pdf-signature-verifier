"""Vendored pdf.js is local; no CDN fallback."""

from __future__ import annotations

import unittest

from support import REPO_ROOT

CDN = "cdnjs.cloudflare.com"
VERSION = "3.11.174"


class PdfJsVendorTests(unittest.TestCase):
    def test_files_exist(self) -> None:
        root = REPO_ROOT / "app" / "static" / "pdfjs"
        self.assertTrue((root / "pdf.min.js").is_file())
        self.assertTrue((root / "pdf.worker.min.js").is_file())
        self.assertIn(VERSION, (root / "VERSION").read_text(encoding="utf-8"))

    def test_html_and_viewer_use_local_paths(self) -> None:
        html = (REPO_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
        js = (REPO_ROOT / "app" / "static" / "viewer.js").read_text(encoding="utf-8")
        self.assertNotIn(CDN, html)
        self.assertNotIn(CDN, js)
        self.assertNotIn("https://", html.split("<body", 1)[0])
        self.assertIn("/static/pdfjs/pdf.min.js", html)
        self.assertIn("/static/pdfjs/pdf.worker.min.js", js)


if __name__ == "__main__":
    unittest.main()
