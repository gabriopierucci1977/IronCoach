"""
Test della configurazione runtime di IronCoach.

Verifica che:

- le soglie di freschezza usino i default previsti;
- le variabili d'ambiente sovrascrivano i default;
- valori vuoti, non interi o negativi ricadano sui default;
- il valore zero sia accettato;
- RuntimeConfig raccolga la configurazione in un oggetto immutabile;
- i getter legacy restino compatibili;
- i parametri espliciti del ContextBuilder abbiano priorità
  sulla configurazione d'ambiente.
"""

from dataclasses import FrozenInstanceError

import pytest

from backend.config import (
    DEFAULT_RECOVERY_MAX_AGE_DAYS,
    DEFAULT_TRAINING_MAX_AGE_DAYS,
    RuntimeConfig,
    get_recovery_max_age_days,
    get_runtime_config,
    get_training_max_age_days,
)
from backend.context_builder import ContextBuilder


class FakeClient:
    def get_athlete_profile(self):
        return {}

    def get_latest_recovery(self):
        return {
            "Data": "2026-08-06",
        }

    def get_latest_training(self):
        return {
            "Data allenamento": "2026-08-06",
            "Sport": "Corsa",
        }

    def get_latest_nutrition(self):
        return {}

    def get_latest_decision(self):
        return {}

    def get_training_history(self):
        return []

    def get_recovery_history(self):
        return []

    def get_performance_history(self):
        return []


class FakeArchive:
    def iter_all(self):
        return iter([])


def _clear_threshold_environment(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        raising=False,
    )
    monkeypatch.delenv(
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        raising=False,
    )


def test_runtime_config_uses_defaults(
    monkeypatch,
) -> None:
    _clear_threshold_environment(
        monkeypatch
    )

    config = get_runtime_config()

    assert config == RuntimeConfig(
        recovery_max_age_days=3,
        training_max_age_days=7,
    )


def test_freshness_threshold_getters_use_defaults(
    monkeypatch,
) -> None:
    _clear_threshold_environment(
        monkeypatch
    )

    assert (
        get_recovery_max_age_days()
        == DEFAULT_RECOVERY_MAX_AGE_DAYS
        == 3
    )
    assert (
        get_training_max_age_days()
        == DEFAULT_TRAINING_MAX_AGE_DAYS
        == 7
    )


def test_environment_overrides_runtime_config(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        "5",
    )
    monkeypatch.setenv(
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        "10",
    )

    config = get_runtime_config()

    assert config.recovery_max_age_days == 5
    assert config.training_max_age_days == 10


def test_legacy_getters_follow_runtime_config(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        "5",
    )
    monkeypatch.setenv(
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        "10",
    )

    assert get_recovery_max_age_days() == 5
    assert get_training_max_age_days() == 10


def test_invalid_environment_values_use_defaults(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        "non-numerico",
    )
    monkeypatch.setenv(
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        "-1",
    )

    config = get_runtime_config()

    assert (
        config.recovery_max_age_days
        == DEFAULT_RECOVERY_MAX_AGE_DAYS
    )
    assert (
        config.training_max_age_days
        == DEFAULT_TRAINING_MAX_AGE_DAYS
    )


def test_empty_environment_values_use_defaults(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        "   ",
    )
    monkeypatch.setenv(
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        "",
    )

    config = get_runtime_config()

    assert (
        config.recovery_max_age_days
        == DEFAULT_RECOVERY_MAX_AGE_DAYS
    )
    assert (
        config.training_max_age_days
        == DEFAULT_TRAINING_MAX_AGE_DAYS
    )


def test_zero_is_a_valid_threshold(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        "0",
    )
    monkeypatch.setenv(
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        "0",
    )

    config = get_runtime_config()

    assert config.recovery_max_age_days == 0
    assert config.training_max_age_days == 0


def test_runtime_config_is_immutable() -> None:
    config = RuntimeConfig()

    with pytest.raises(
        FrozenInstanceError
    ):
        config.recovery_max_age_days = 4


def test_context_builder_reads_environment_thresholds(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        "4",
    )
    monkeypatch.setenv(
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        "9",
    )

    builder = ContextBuilder(
        FakeClient(),
        garmin_archive=FakeArchive(),
    )

    assert builder.recovery_max_age_days == 4
    assert builder.training_max_age_days == 9


def test_explicit_builder_thresholds_override_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        "4",
    )
    monkeypatch.setenv(
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        "9",
    )

    builder = ContextBuilder(
        FakeClient(),
        garmin_archive=FakeArchive(),
        recovery_max_age_days=2,
        training_max_age_days=6,
    )

    assert builder.recovery_max_age_days == 2
    assert builder.training_max_age_days == 6


def test_invalid_explicit_thresholds_use_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        "4",
    )
    monkeypatch.setenv(
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        "9",
    )

    builder = ContextBuilder(
        FakeClient(),
        garmin_archive=FakeArchive(),
        recovery_max_age_days=-1,
        training_max_age_days="non-numerico",
    )

    assert builder.recovery_max_age_days == 4
    assert builder.training_max_age_days == 9