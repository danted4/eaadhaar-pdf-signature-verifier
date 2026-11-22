"""Vendored pdf.js is local; no CDN fallback."""

from __future__ import annotations

import re
import unittest

from support import REPO_ROOT

CDN = "cdnjs.cloudflare.com"
VERSION = "3.11.174"


def _strip_js_comments(js: str) -> str:
    """Drop /* */ and // comments so prose cannot satisfy or trip a check."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$|\s//\s.*$", "", js)


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

    def test_viewer_disables_pdfjs_eval(self) -> None:
        # CVE-2024-4367: pdf.js 3.11.174 compiles font matrices with eval
        # unless isEvalSupported is false. Strip comments so a comment that
        # mentions the option cannot satisfy the check.
        js = (REPO_ROOT / "app" / "static" / "viewer.js").read_text(encoding="utf-8")
        code = _strip_js_comments(js)
        calls = re.findall(r"getDocument\s*\(([^)]*)\)", code)
        self.assertTrue(calls, "no pdfjsLib.getDocument call found")
        for args in calls:
            self.assertRegex(args, r"^\s*\{", f"getDocument must take an options object: {args}")
            self.assertRegex(args, r"\bisEvalSupported\s*:\s*false\b", args)

    def test_viewer_has_no_inline_styles(self) -> None:
        # The CSP has style-src 'self' (no 'unsafe-inline'), so inline <style>
        # blocks and style attributes would be silently dropped.
        js = _strip_js_comments((REPO_ROOT / "app" / "static" / "viewer.js").read_text(encoding="utf-8"))
        html = (REPO_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
        for name, text in (("viewer.js", js), ("index.html", html)):
            with self.subTest(name):
                self.assertNotRegex(text, r"<style\b")
                self.assertNotRegex(text, r"""setAttribute\(\s*["']style["']""")
                self.assertNotRegex(text, r"""\sstyle\s*=\s*["']""")
        self.assertIn("/static/print-frame.css", js)
        self.assertTrue((REPO_ROOT / "app" / "static" / "print-frame.css").is_file())


if __name__ == "__main__":
    unittest.main()
