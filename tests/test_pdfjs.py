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

    def test_ui_strings_have_no_em_dashes(self) -> None:
        # User-facing text only. stamp-render.js's tick-point labels are for
        # the stamp lab and mirror prototype/stamp-render.js, so they're exempt.
        for path in (STATIC / "viewer.js", STATIC / "index.html"):
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".js":
                text = _strip_js_comments(text)
            with self.subTest(path.name):
                self.assertNotIn("\u2014", text)

    def test_docbar_alert_is_announced(self) -> None:
        # Post-preview errors render here (showError in viewer.js); role=alert
        # makes screen readers announce them.
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'<div id="docbar-alert"[^>]*\brole="alert"[^>]*\bhidden\b')
        # .docbar-sub styles the verdict/reason line above the alert.
        self.assertIn('id="docbar-sub" class="docbar-sub"', html)

    def test_stamp_fallback_never_claims_uidai(self) -> None:
        # bodyLines() falls back when a PDF has no Acrobat body lines (never an
        # e-Aadhaar). It must name the real signer, not UIDAI.
        js = _strip_js_comments((STATIC / "viewer.js").read_text(encoding="utf-8"))
        body = re.search(r"function bodyLines\(widget\) \{([\s\S]*?)\n\}", js)
        self.assertIsNotNone(body, "bodyLines() not found")
        self.assertNotIn("Identification Authority", body.group(1))
        self.assertIn("cnFromSigner(widget.signer)", body.group(1))

    def test_header_and_docbar_are_sticky(self) -> None:
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        for selector in (".chrome", ".docbar"):
            block = re.search(re.escape(selector) + r" \{([^}]*)\}", css)
            self.assertIsNotNone(block, selector)
            self.assertIn("position: sticky", block.group(1), selector)
        self.assertRegex(css, r"\.docbar \{[^}]*top: var\(--chrome-h\)")

    def test_form_slots_are_fixed(self) -> None:
        # Fixed slots: the password field is always present but starts disabled
        # (enabled only once pdf.js says the PDF needs one), and Preview is
        # always present but starts disabled; nothing is shown or hidden.
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'<input type="password" id="password"[^>]*\bdisabled>')
        self.assertRegex(html, r'<button type="submit" id="previewBtn"[^>]*\bdisabled>')
        self.assertNotRegex(html, r'id="(password|previewBtn|passwordField|filePick)"[^>]*\bhidden\b')
        js = _strip_js_comments((STATIC / "viewer.js").read_text(encoding="utf-8"))
        self.assertIn('err?.name === "PasswordException"', js)

    def test_upload_form_accessibility(self) -> None:
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'<input type="password" id="password"[^>]*aria-describedby="passwordHint"')
        self.assertRegex(html, r'<p id="passwordHint"[^>]*aria-live="polite"')
        self.assertRegex(html, r'<p id="error"[^>]*role="alert"')
        # display:none would take the file input out of the tab order.
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"\.file input \{[^}]*display:\s*none")

    def test_client_upload_cap_matches_server(self) -> None:
        import sys

        sys.path.insert(0, str(REPO_ROOT / "app"))
        import server  # noqa: E402

        js = (STATIC / "viewer.js").read_text(encoding="utf-8")
        match = re.search(r"const MAX_UPLOAD_BYTES = ([\d\s*]+);", js)
        self.assertIsNotNone(match, "MAX_UPLOAD_BYTES not found in viewer.js")
        factors = [int(f) for f in match.group(1).split("*")]
        product = 1
        for f in factors:
            product *= f
        self.assertEqual(product, server.MAX_UPLOAD_BYTES)


if __name__ == "__main__":
    unittest.main()
