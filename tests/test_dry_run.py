from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_run_py_dry_run_exits_zero() -> None:
    root = Path(__file__).resolve().parent.parent
    run_py = root / "run.py"
    proc = subprocess.run(
        [sys.executable, str(run_py), "--dry-run"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_only_discovery_dry_run() -> None:
    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, str(root / "run.py"), "--dry-run", "--only-discovery"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
