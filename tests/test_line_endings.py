"""Line-ending invariants for shell launchers."""

from __future__ import annotations

import unittest

from support import REPO_ROOT


class LineEndingTests(unittest.TestCase):
    def test_setup_sh_is_lf_only(self) -> None:
        data = (REPO_ROOT / "setup.sh").read_bytes()
        self.assertNotIn(b"\r", data)

    def test_everify_app_is_lf_only(self) -> None:
        data = (REPO_ROOT / "everify-app").read_bytes()
        self.assertNotIn(b"\r", data)

    def test_gitattributes_keeps_sh_lf_and_bat_crlf(self) -> None:
        text = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.sh text eol=lf", text)
        self.assertIn("*.bat text eol=crlf", text)


if __name__ == "__main__":
    unittest.main()
