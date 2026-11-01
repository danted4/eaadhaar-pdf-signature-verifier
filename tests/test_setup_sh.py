"""Hermetic tests for setup.sh Python detection (stub binaries, temp dirs)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import (
    fill_tool_bin,
    isolated_env,
    run_bash,
    seed_setup_project,
    write_python_stub,
)


class SetupShTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.project = self.root / "project"
        self.stub_bin = self.root / "bin"
        self.tools_bin = fill_tool_bin(self.root / "tools")
        self.log = self.root / "python.log"
        self.project.mkdir()
        self.stub_bin.mkdir()
        seed_setup_project(self.project)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _env(self) -> dict[str, str]:
        return isolated_env(
            self.stub_bin,
            self.tools_bin,
            extra={"PYTHON_STUB_LOG": str(self.log)},
        )

    def _run(self):
        return run_bash(self.project / "setup.sh", cwd=self.project, env=self._env())

    def _log(self) -> str:
        if not self.log.exists():
            return ""
        return self.log.read_text(encoding="utf-8")

    def test_prefers_python3_when_both_are_new_enough(self) -> None:
        write_python_stub(self.stub_bin, "python3", "3.12")
        write_python_stub(self.stub_bin, "python", "3.11")
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Using python3 (Python 3.12)", result.stdout)
        self.assertIn("Setup complete", result.stdout)
        self.assertTrue((self.project / ".venv" / "bin" / "python").exists())

    def test_falls_back_to_python_when_python3_is_missing(self) -> None:
        write_python_stub(self.stub_bin, "python", "3.10")
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Using python (Python 3.10)", result.stdout)

    def test_fails_when_neither_command_exists(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("tried python3, then python", result.stderr)
        self.assertFalse((self.project / ".venv").exists())

    def test_fails_when_only_python_is_too_old(self) -> None:
        write_python_stub(self.stub_bin, "python", "3.9")
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("too old", result.stderr)
        self.assertIn("Python 3.10+", result.stderr)
        self.assertFalse((self.project / ".venv").exists())

    def test_falls_back_to_python_when_python3_is_too_old(self) -> None:
        write_python_stub(self.stub_bin, "python3", "3.9")
        write_python_stub(self.stub_bin, "python", "3.12")
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Using python (Python 3.12)", result.stdout)
        names = [
            line.split()[0].rsplit("/", 1)[-1]
            for line in self._log().splitlines()
            if line.strip()
        ]
        self.assertIn("python3", names)
        self.assertIn("python", names)

    def test_missing_trust_roots_fail_after_python_check(self) -> None:
        (self.project / "certs" / "CCAIndia2022.cer").unlink()
        (self.project / "certs" / "CCAIndia2022SPL.cer").unlink()
        write_python_stub(self.stub_bin, "python3", "3.12")
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("CCAIndia2022.cer not found", result.stderr)
        self.assertIn("Using python3", result.stdout)


if __name__ == "__main__":
    unittest.main()
