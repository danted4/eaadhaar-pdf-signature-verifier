"""Vendored pdf.js is local; no CDN fallback."""

from __future__ import annotations

import re
import unittest

from support import REPO_ROOT

CDN = "cdnjs.cloudflare.com"
VERSION = "3.11.174"


STATIC = REPO_ROOT / "app" / "static"


def _strip_js_comments(js: str) -> str:
    """Drop comments so prose cannot satisfy or trip a check.

    A comment must start a line or follow whitespace, so string contents such
    as "image/*" or "https://" are not mistaken for comment openers.
    """
    js = re.sub(r"(?:^|(?<=\s))/\*.*?\*/", "", js, flags=re.S | re.M)
    return re.sub(r"(?:^|(?<=\s))//.*$", "", js, flags=re.M)


def _call_args(code: str, name: str) -> list[str]:
    """Return the full argument text of each `name(...)` call, matching nesting."""
    out = []
    for match in re.finditer(rf"\b{re.escape(name)}\s*\(", code):
        depth, i = 1, match.end()
        while depth and i < len(code):
            depth += {"(": 1, ")": -1}.get(code[i], 0)
            i += 1
        out.append(code[match.end() : i - 1])
    return out


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
        # unless isEvalSupported is false. Comments are stripped so a comment
        # that mentions the option cannot satisfy the check.
        code = _strip_js_comments((STATIC / "viewer.js").read_text(encoding="utf-8"))
        calls = _call_args(code, "getDocument")
        self.assertTrue(calls, "no pdfjsLib.getDocument call found")
        for args in calls:
            with self.subTest(args=args):
                self.assertRegex(args, r"^\s*\{[\s\S]*\}\s*$", "getDocument must take an object literal")
                self.assertRegex(args, r"\bisEvalSupported\s*:\s*false\b")
                # A spread could override the option at runtime.
                self.assertNotIn("...", args)

    def test_no_inline_styles(self) -> None:
        # The CSP has style-src 'self' (no 'unsafe-inline'), so inline <style>
        # blocks and style attributes would be silently dropped.
        files = sorted(STATIC.glob("*.js")) + [STATIC / "index.html"]
        self.assertIn(STATIC / "viewer.js", files)
        for path in files:
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".js":
                text = _strip_js_comments(text)
            with self.subTest(path.name):
                self.assertNotRegex(text, r"<style\b")
                self.assertNotRegex(text, r"""setAttribute\(\s*["']style["']""")
                self.assertNotRegex(text, r"""\sstyle\s*=\s*["']""")
        self.assertIn("/static/print-frame.css", (STATIC / "viewer.js").read_text(encoding="utf-8"))
        self.assertTrue((STATIC / "print-frame.css").is_file())

if __name__ == "__main__":
    unittest.main()
