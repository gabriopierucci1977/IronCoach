"""
Configurazione runtime di IronCoach.

Le soglie di freschezza possono essere personalizzate tramite:

- IRONCOACH_RECOVERY_MAX_AGE_DAYS
- IRONCOACH_TRAINING_MAX_AGE_DAYS

Valori assenti, non interi o negativi ricadono sui default.
"""

from __future__ import annotations

import os


DEFAULT_RECOVERY_MAX_AGE_DAYS = 3
DEFAULT_TRAINING_MAX_AGE_DAYS = 7


def _non_negative_int_from_env(
    name: str,
    default: int,
) -> int:
    raw_value = os.getenv(
        name,
        "",
    ).strip()

    if not raw_value:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        return default

    if value < 0:
        return default

    return value


def get_recovery_max_age_days() -> int:
    return _non_negative_int_from_env(
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        DEFAULT_RECOVERY_MAX_AGE_DAYS,
    )


def get_training_max_age_days() -> int:
    return _non_negative_int_from_env(
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        DEFAULT_TRAINING_MAX_AGE_DAYS,
    )