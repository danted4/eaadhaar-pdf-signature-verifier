"""Static contracts for Windows .bat launchers (no cmd.exe required)."""

from __future__ import annotations

import re
import unittest

from support import REPO_ROOT


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


class SetupBatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm((REPO_ROOT / "setup.bat").read_text(encoding="ascii"))

    def test_tries_python3_before_python(self) -> None:
        py3 = self.text.index("python3 --version")
        py = self.text.index("\npython --version")
        self.assertLess(py3, py)

    def test_requires_python_3_10(self) -> None:
        self.assertIn("sys.version_info >= (3, 10)", self.text)
        self.assertIn("Python 3.10+ is required", self.text)

    def test_python_probe_uses_errorlevel_not_percent_expansion(self) -> None:
        head = self.text.split(":have_python", 1)[0]
        self.assertIn("if not errorlevel 1", head)
        self.assertNotIn("%ERRORLEVEL%", head)

    def test_python3_too_old_still_tries_python(self) -> None:
        py3_check = self.text.index(
            'python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"'
        )
        py_probe = self.text.index("\npython --version")
        self.assertLess(py3_check, py_probe)
        between = self.text[py3_check:py_probe]
        self.assertNotIn("exit /b 1", between)


class EverifyAppBatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (REPO_ROOT / "everify-app.bat").read_bytes()
        self.text = _norm(self.raw.decode("ascii"))

    def test_tries_python_exe_before_python3_exe(self) -> None:
        py = self.text.index('.venv\\Scripts\\python.exe')
        py3 = self.text.index('.venv\\Scripts\\python3.exe')
        self.assertLess(py, py3)

    def test_if_exist_blocks_do_not_expand_errorlevel_at_parse_time(self) -> None:
        blocks = re.findall(r"if exist .*?\((.*?)\)", self.text, flags=re.S | re.I)
        self.assertGreaterEqual(len(blocks), 2)
        for body in blocks:
            self.assertNotIn(
                "%ERRORLEVEL%",
                body,
                "cmd.exe expands %ERRORLEVEL% when the (...) block is parsed",
            )

    def test_propagates_python_exit_code_outside_if_block(self) -> None:
        self.assertIn("goto :propagate_exit", self.text)
        self.assertRegex(self.text, r":propagate_exit\nexit /b %ERRORLEVEL%")

    def test_missing_venv_exits_1(self) -> None:
        self.assertIn("if not exist \".venv\"", self.text)
        self.assertIn("exit /b 1", self.text)

    def test_crlf_line_endings(self) -> None:
        self.assertIn(b"\r\n", self.raw)
        self.assertNotIn(b"\n", self.raw.replace(b"\r\n", b""))


class SetupBatLineEndingsTests(unittest.TestCase):
    def test_setup_bat_is_crlf(self) -> None:
        raw = (REPO_ROOT / "setup.bat").read_bytes()
        self.assertIn(b"\r\n", raw)
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))


if __name__ == "__main__":
    unittest.main()
