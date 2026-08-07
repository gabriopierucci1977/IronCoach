"""
Configurazione runtime di IronCoach.

Le soglie di freschezza e i limiti di confidenza possono essere
personalizzati tramite:

- IRONCOACH_RECOVERY_MAX_AGE_DAYS
- IRONCOACH_TRAINING_MAX_AGE_DAYS
- IRONCOACH_FRESHNESS_HIGH_CONFIDENCE_CAP
- IRONCOACH_FRESHNESS_MODERATE_CONFIDENCE_CAP

Valori assenti, non interi o fuori intervallo ricadono sui default.

I cap di confidenza rispettano sempre la relazione:

0 <= HIGH <= MODERATE <= 100
"""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_RECOVERY_MAX_AGE_DAYS = 3
DEFAULT_TRAINING_MAX_AGE_DAYS = 7
DEFAULT_FRESHNESS_HIGH_CONFIDENCE_CAP = 75
DEFAULT_FRESHNESS_MODERATE_CONFIDENCE_CAP = 85


def _bounded_int_from_env(
    name: str,
    default: int,
    minimum: int,
    maximum: int,
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

    if value < minimum or value > maximum:
        return default

    return value


def _non_negative_int_from_env(
    name: str,
    default: int,
) -> int:
    return _bounded_int_from_env(
        name=name,
        default=default,
        minimum=0,
        maximum=2_147_483_647,
    )


def _normalize_confidence_cap(
    value: int,
    default: int,
) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return default

    if resolved < 0 or resolved > 100:
        return default

    return resolved


@dataclass(frozen=True)
class RuntimeConfig:
    recovery_max_age_days: int = (
        DEFAULT_RECOVERY_MAX_AGE_DAYS
    )
    training_max_age_days: int = (
        DEFAULT_TRAINING_MAX_AGE_DAYS
    )
    freshness_high_confidence_cap: int = (
        DEFAULT_FRESHNESS_HIGH_CONFIDENCE_CAP
    )
    freshness_moderate_confidence_cap: int = (
        DEFAULT_FRESHNESS_MODERATE_CONFIDENCE_CAP
    )

    def __post_init__(self) -> None:
        high_cap = _normalize_confidence_cap(
            self.freshness_high_confidence_cap,
            DEFAULT_FRESHNESS_HIGH_CONFIDENCE_CAP,
        )
        moderate_cap = _normalize_confidence_cap(
            self.freshness_moderate_confidence_cap,
            DEFAULT_FRESHNESS_MODERATE_CONFIDENCE_CAP,
        )

        high_cap = min(
            high_cap,
            moderate_cap,
        )

        object.__setattr__(
            self,
            "freshness_high_confidence_cap",
            high_cap,
        )
        object.__setattr__(
            self,
            "freshness_moderate_confidence_cap",
            moderate_cap,
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
            freshness_high_confidence_cap=(
                _bounded_int_from_env(
                    "IRONCOACH_FRESHNESS_HIGH_CONFIDENCE_CAP",
                    DEFAULT_FRESHNESS_HIGH_CONFIDENCE_CAP,
                    minimum=0,
                    maximum=100,
                )
            ),
            freshness_moderate_confidence_cap=(
                _bounded_int_from_env(
                    "IRONCOACH_FRESHNESS_MODERATE_CONFIDENCE_CAP",
                    DEFAULT_FRESHNESS_MODERATE_CONFIDENCE_CAP,
                    minimum=0,
                    maximum=100,
                )
            ),
        )


def get_runtime_config() -> RuntimeConfig:
    return RuntimeConfig.from_env()