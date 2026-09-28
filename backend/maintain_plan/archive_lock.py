"""Cross-process advisory lock for MAINTAIN_PLAN SQLite access."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import fcntl
import sqlite3


def lock_path(database_path: str | Path) -> Path:
    path = Path(database_path)
    return path.with_name(f"{path.name}.ironcoach.lock")


@contextmanager
def archive_lock(database_path: str | Path):
    """Exclude repository connections while an archive snapshot is copied."""
    path = lock_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
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
