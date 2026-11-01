"""Helpers for hermetic launcher tests (no network, no real .venv)."""

from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STUB_IMPL = Path(__file__).resolve().parent / "python_stub.sh"
BASH = shutil.which("bash") or "/bin/bash"

_PATH_TOOLS = (
    "dirname",
    "pwd",
    "chmod",
    "mkdir",
    "cp",
    "rm",
    "cat",
    "ln",
    "bash",
    "env",
    "uname",
)


def fill_tool_bin(tools_bin: Path) -> Path:
    """Copy/symlink core utilities so tests can omit /usr/bin (and its python3)."""
    tools_bin.mkdir(parents=True, exist_ok=True)
    for name in _PATH_TOOLS:
        dest = tools_bin / name
        if dest.exists():
            continue
        src = shutil.which(name)
        if src:
            dest.symlink_to(src)
    return tools_bin


def isolated_env(*path_dirs: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    path = ":".join(str(p) for p in path_dirs if p) + ":/bin"
    home = path_dirs[-1] if path_dirs else Path("/tmp")
    env = {
        "PATH": path,
        "HOME": str(home),
        "TERM": "dumb",
        "LANG": "C",
        "LC_ALL": "C",
    }
    if extra:
        env.update(extra)
    return env


def write_python_stub(stub_bin: Path, name: str, version: str) -> Path:
    stub_bin.mkdir(parents=True, exist_ok=True)
    path = stub_bin / name
    path.write_text(
        "#!/bin/bash\n"
        f'export PYTHON_STUB_VERSION="{version}"\n'
        f'export PYTHON_STUB_SELF="{path}"\n'
        f'exec /bin/bash "{STUB_IMPL}" "$@"\n',
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def seed_setup_project(project: Path, *, certs: bool = True) -> None:
    shutil.copy(REPO_ROOT / "setup.sh", project / "setup.sh")
    (project / "requirements.txt").write_text("placeholder\n", encoding="utf-8")
    (project / "everify-app").write_text("#!/bin/bash\necho stub-launcher\n", encoding="utf-8")
    if certs:
        (project / "CCAIndia2022.cer").write_bytes(b"dummy-cert")
        (project / "CCAIndia2022SPL.cer").write_bytes(b"dummy-cert")


def seed_launcher_project(project: Path) -> None:
    shutil.copy(REPO_ROOT / "everify-app", project / "everify-app")
    launcher = project / "everify-app"
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    (project / "app").mkdir(parents=True, exist_ok=True)
    (project / "app" / "server.py").write_text("# test placeholder\n", encoding="utf-8")


def run_bash(
    script: Path,
    *,
    cwd: Path,
    env: dict[str, str],
    args: list[str] | None = None,
    timeout: float = 10,
) -> subprocess.CompletedProcess[str]:
    cmd = [BASH, str(script), *(args or [])]
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def make_venv_interpreter(project: Path, name: str, version: str = "3.12") -> Path:
    bin_dir = project / ".venv" / "bin"
    return write_python_stub(bin_dir, name, version)
