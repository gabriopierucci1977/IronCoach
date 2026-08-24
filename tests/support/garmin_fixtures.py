"""Helpers for optional local Garmin FIT regression fixtures.

The real Garmin FIT samples contain athlete data and are intentionally not
committed to the public repository. Tests that validate byte-level FIT
parsing use this helper so a clean clone reports them as skipped instead of
failing because a private fixture is absent.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


DEFAULT_FIXTURE_DIR = Path("data/garmin_raw")
ENV_FIXTURE_DIR = "IRONCOACH_GARMIN_FIXTURE_DIR"


def fixture_path(filename: str) -> Path:
    root = Path(
        os.getenv(
            ENV_FIXTURE_DIR,
            str(DEFAULT_FIXTURE_DIR),
        )
    )
    return root / filename


def require_garmin_fixture(filename: str) -> str:
    path = fixture_path(filename)

    if not path.is_file():
        pytest.skip(
            "Fixture Garmin privata non disponibile: "
            f"{path}. Impostare {ENV_FIXTURE_DIR} oppure copiare il file "
            "in data/garmin_raw per eseguire questo test."
        )

    return str(path)
