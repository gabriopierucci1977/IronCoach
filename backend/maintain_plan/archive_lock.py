"""Cross-process advisory lock for MAINTAIN_PLAN SQLite access."""

from __future__ import annotations

from contextlib import contextmanager
import errno
from hashlib import sha256
from pathlib import Path
import os
import sqlite3
import sys
import tempfile
import time

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import msvcrt
else:
    import fcntl


def _lock(handle) -> None:
    if not _IS_WINDOWS:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return

    # Windows locks byte ranges rather than whole files.  All IronCoach
    # processes use the first byte, and LK_NBLCK lets us wait indefinitely
    # (LK_LOCK only retries for a limited period in the Python runtime).
    handle.seek(0)
    if not handle.read(1):
        handle.seek(0)
        handle.write(b"\0")
        handle.flush()
    while True:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        except OSError as error:
            if error.errno not in {errno.EACCES, errno.EDEADLK} and getattr(
                error, "winerror", None
            ) not in {33, 36}:
                raise
            time.sleep(0.05)


def _unlock(handle) -> None:
    if _IS_WINDOWS:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def lock_path(database_path: str | Path) -> Path:
    canonical = str(Path(database_path).resolve()).encode("utf-8")
    digest = sha256(canonical).hexdigest()
    user = str(os.getuid()) if hasattr(os, "getuid") else "default"
    directory = Path(tempfile.gettempdir()) / f"ironcoach-maintain-plan-locks-{user}"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return directory / f"{digest}.lock"


@contextmanager
def archive_lock(database_path: str | Path):
    """Exclude repository connections while an archive snapshot is copied."""
    path = lock_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        _lock(handle)
        yield
    finally:
        try:
            _unlock(handle)
        finally:
            handle.close()


class LockedConnection(sqlite3.Connection):
    _archive_lock_context = None

    def close(self) -> None:
        context = self._archive_lock_context
        if context is None:
            return super().close()
        self._archive_lock_context = None
        try:
            super().close()
        finally:
            context.__exit__(None, None, None)

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def locked_connect(database_path: str | Path) -> LockedConnection:
    context = archive_lock(database_path)
    context.__enter__()
    try:
        connection = sqlite3.connect(database_path, factory=LockedConnection)
    except Exception:
        context.__exit__(None, None, None)
        raise
    connection._archive_lock_context = context
    return connection
