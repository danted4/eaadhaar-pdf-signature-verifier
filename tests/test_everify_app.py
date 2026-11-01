"""Hermetic tests for the Unix everify-app launcher."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import (
    fill_tool_bin,
    isolated_env,
    make_venv_interpreter,
    run_bash,
    seed_launcher_project,
)


class EverifyAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        seed_launcher_project(self.project)
        self.tools_bin = fill_tool_bin(self.root / "tools")
        self.log = self.root / "python.log"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        merged = {"PYTHON_STUB_LOG": str(self.log)}
        if extra:
            merged.update(extra)
        return isolated_env(self.project / ".venv" / "bin", self.tools_bin, extra=merged)

    def _run(self, args: list[str] | None = None, env: dict[str, str] | None = None):
        return run_bash(
            self.project / "everify-app",
            cwd=self.project,
            env=env or self._env(),
            args=args,
        )

    def test_missing_venv_exits_1(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".venv not found", result.stderr)

    def test_prefers_venv_python3(self) -> None:
        make_venv_interpreter(self.project, "python3", "3.12")
        make_venv_interpreter(self.project, "python", "3.11")
        result = self._run(env=self._env({"PYTHON_STUB_EXIT": "17"}))
        self.assertEqual(result.returncode, 17, result.stderr)
        log = self.log.read_text(encoding="utf-8")
        self.assertIn(".venv/bin/python3", log)
        self.assertIn("app/server.py", log)
        self.assertNotIn(".venv/bin/python ", log)

    def test_falls_back_to_venv_python(self) -> None:
        make_venv_interpreter(self.project, "python", "3.12")
        result = self._run(env=self._env({"PYTHON_STUB_EXIT": "5"}))
        self.assertEqual(result.returncode, 5, result.stderr)
        log = self.log.read_text(encoding="utf-8")
        self.assertIn(".venv/bin/python ", log)
        self.assertIn("app/server.py", log)

    def test_nonexecutable_python3_falls_back_to_python(self) -> None:
        py3 = make_venv_interpreter(self.project, "python3", "3.12")
        py3.chmod(0o644)
        make_venv_interpreter(self.project, "python", "3.12")
        result = self._run(env=self._env({"PYTHON_STUB_EXIT": "0"}))
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log.read_text(encoding="utf-8")
        self.assertIn(".venv/bin/python ", log)

    def test_missing_interpreters_exits_1(self) -> None:
        (self.project / ".venv" / "bin").mkdir(parents=True)
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("tried python3, then python", result.stderr)

    def test_forwards_arguments(self) -> None:
        make_venv_interpreter(self.project, "python3", "3.12")
        result = self._run(["--bind", "127.0.0.1"])
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log.read_text(encoding="utf-8")
        self.assertIn("--bind", log)
        self.assertIn("127.0.0.1", log)


if __name__ == "__main__":
    unittest.main()
