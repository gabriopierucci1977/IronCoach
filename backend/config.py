"""
Configurazione runtime di IronCoach.

Le soglie di freschezza possono essere personalizzate tramite:

- IRONCOACH_RECOVERY_MAX_AGE_DAYS
- IRONCOACH_TRAINING_MAX_AGE_DAYS

Valori assenti, non interi o negativi ricadono sui default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


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


@dataclass(frozen=True)
class RuntimeConfig:
    recovery_max_age_days: int = (
        DEFAULT_RECOVERY_MAX_AGE_DAYS
    )
    training_max_age_days: int = (
        DEFAULT_TRAINING_MAX_AGE_DAYS
    )

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        return cls(
            recovery_max_age_days=(
                _non_negative_int_from_env(
                    "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
                    DEFAULT_RECOVERY_MAX_AGE_DAYS,
                )
            ),
            training_max_age_days=(
                _non_negative_int_from_env(
                    "IRONCOACH_TRAINING_MAX_AGE_DAYS",
                    DEFAULT_TRAINING_MAX_AGE_DAYS,
                )
            ),
        )


def get_runtime_config() -> RuntimeConfig:
    return RuntimeConfig.from_env()


def get_recovery_max_age_days() -> int:
    return (
        get_runtime_config()
        .recovery_max_age_days
    )


def get_training_max_age_days() -> int:
    return (
        get_runtime_config()
        .training_max_age_days
    )