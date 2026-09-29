import subprocess
import sys
import time
from pathlib import Path

from backend.maintain_plan.archive_lock import archive_lock


def test_archive_lock_preserves_cross_process_exclusion(tmp_path: Path) -> None:
    database = tmp_path / "archive.sqlite"
    script = (
        "from backend.maintain_plan.archive_lock import archive_lock; "
        f"p = {str(database)!r}; "
        "\nwith archive_lock(p):\n print('locked', flush=True)\n"
    )

    with archive_lock(database):
        child = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert child.stdout is not None
            time.sleep(0.2)
            assert child.poll() is None
        finally:
            if child.poll() is not None and child.returncode != 0:
                child.wait()

    output, _ = child.communicate(timeout=5)
    assert child.returncode == 0
    assert output == "locked\n"


def test_repository_import_uses_windows_lock_backend_without_fcntl() -> None:
    script = r'''
import builtins
import os
import sys
import tempfile
import types

real_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name == "fcntl":
        raise ModuleNotFoundError("No module named 'fcntl'")
    return real_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
sys.platform = "win32"
calls = []
sys.modules["msvcrt"] = types.SimpleNamespace(
    LK_NBLCK=1,
    LK_UNLCK=0,
    locking=lambda *args: calls.append(args),
)
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.archive_lock import _lock, _unlock

assert MaintainPlanRepository.__name__ == "MaintainPlanRepository"
with tempfile.TemporaryFile(mode="w+b") as handle:
    _lock(handle)
    _unlock(handle)
assert [call[1:] for call in calls] == [(1, 1), (0, 1)]
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
