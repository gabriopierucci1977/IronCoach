"""
Test della configurazione runtime di IronCoach.

Verifica che:

- le soglie di freschezza usino i default previsti;
- le variabili d'ambiente sovrascrivano i default;
- valori vuoti, non interi o negativi ricadano sui default;
- il valore zero sia accettato;
- i cap di confidenza rispettino sempre HIGH <= MODERATE;
- RuntimeConfig raccolga la configurazione in un oggetto immutabile;
- i parametri espliciti del ContextBuilder abbiano priorità
  sulla configurazione d'ambiente.
"""

from dataclasses import FrozenInstanceError

import pytest

from backend.config import (
    DEFAULT_FRESHNESS_HIGH_CONFIDENCE_CAP,
    DEFAULT_FRESHNESS_MODERATE_CONFIDENCE_CAP,
    DEFAULT_RECOVERY_MAX_AGE_DAYS,
    DEFAULT_TRAINING_MAX_AGE_DAYS,
    RuntimeConfig,
    get_runtime_config,
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


def _clear_runtime_environment(
    monkeypatch,
) -> None:
    for name in (
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        "IRONCOACH_FRESHNESS_HIGH_CONFIDENCE_CAP",
        "IRONCOACH_FRESHNESS_MODERATE_CONFIDENCE_CAP",
    ):
        monkeypatch.delenv(
            name,
            raising=False,
        )


def test_runtime_config_uses_defaults(
    monkeypatch,
) -> None:
    _clear_runtime_environment(
        monkeypatch
    )

    config = get_runtime_config()

    assert config == RuntimeConfig(
        recovery_max_age_days=3,
        training_max_age_days=7,
        freshness_high_confidence_cap=75,
        freshness_moderate_confidence_cap=85,
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
    monkeypatch.setenv(
        "IRONCOACH_FRESHNESS_HIGH_CONFIDENCE_CAP",
        "70",
    )
    monkeypatch.setenv(
        "IRONCOACH_FRESHNESS_MODERATE_CONFIDENCE_CAP",
        "80",
    )

    config = get_runtime_config()

    assert config.recovery_max_age_days == 5
    assert config.training_max_age_days == 10
    assert config.freshness_high_confidence_cap == 70
    assert config.freshness_moderate_confidence_cap == 80


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
    monkeypatch.setenv(
        "IRONCOACH_FRESHNESS_HIGH_CONFIDENCE_CAP",
        "101",
    )
    monkeypatch.setenv(
        "IRONCOACH_FRESHNESS_MODERATE_CONFIDENCE_CAP",
        "non-numerico",
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
    assert (
        config.freshness_high_confidence_cap
        == DEFAULT_FRESHNESS_HIGH_CONFIDENCE_CAP
    )
    assert (
        config.freshness_moderate_confidence_cap
        == DEFAULT_FRESHNESS_MODERATE_CONFIDENCE_CAP
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
    monkeypatch.setenv(
        "IRONCOACH_FRESHNESS_HIGH_CONFIDENCE_CAP",
        "",
    )
    monkeypatch.setenv(
        "IRONCOACH_FRESHNESS_MODERATE_CONFIDENCE_CAP",
        "   ",
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
    assert (
        config.freshness_high_confidence_cap
        == DEFAULT_FRESHNESS_HIGH_CONFIDENCE_CAP
    )
    assert (
        config.freshness_moderate_confidence_cap
        == DEFAULT_FRESHNESS_MODERATE_CONFIDENCE_CAP
    )


def test_zero_is_a_valid_threshold_and_cap(
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
    monkeypatch.setenv(
        "IRONCOACH_FRESHNESS_HIGH_CONFIDENCE_CAP",
        "0",
    )
    monkeypatch.setenv(
        "IRONCOACH_FRESHNESS_MODERATE_CONFIDENCE_CAP",
        "0",
    )

    config = get_runtime_config()

    assert config.recovery_max_age_days == 0
    assert config.training_max_age_days == 0
    assert config.freshness_high_confidence_cap == 0
    assert config.freshness_moderate_confidence_cap == 0


def test_incoherent_environment_caps_are_normalized(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "IRONCOACH_FRESHNESS_HIGH_CONFIDENCE_CAP",
        "90",
    )
    monkeypatch.setenv(
        "IRONCOACH_FRESHNESS_MODERATE_CONFIDENCE_CAP",
        "70",
    )

    config = get_runtime_config()

    assert config.freshness_high_confidence_cap == 70
    assert config.freshness_moderate_confidence_cap == 70


def test_incoherent_direct_caps_are_normalized() -> None:
    config = RuntimeConfig(
        freshness_high_confidence_cap=95,
        freshness_moderate_confidence_cap=80,
    )

    assert config.freshness_high_confidence_cap == 80
    assert config.freshness_moderate_confidence_cap == 80


def test_invalid_direct_caps_use_defaults() -> None:
    config = RuntimeConfig(
        freshness_high_confidence_cap="non-numerico",
        freshness_moderate_confidence_cap=101,
    )

    assert (
        config.freshness_high_confidence_cap
        == DEFAULT_FRESHNESS_HIGH_CONFIDENCE_CAP
    )
    assert (
        config.freshness_moderate_confidence_cap
        == DEFAULT_FRESHNESS_MODERATE_CONFIDENCE_CAP
    )


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


def test_context_builder_uses_explicit_runtime_config(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "IRONCOACH_RECOVERY_MAX_AGE_DAYS",
        "20",
    )
    monkeypatch.setenv(
        "IRONCOACH_TRAINING_MAX_AGE_DAYS",
        "30",
    )

    runtime_config = RuntimeConfig(
        recovery_max_age_days=4,
        training_max_age_days=9,
    )

    builder = ContextBuilder(
        FakeClient(),
        garmin_archive=FakeArchive(),
        runtime_config=runtime_config,
    )

    assert builder.runtime_config is runtime_config
    assert builder.recovery_max_age_days == 4
    assert builder.training_max_age_days == 9


def test_explicit_thresholds_override_runtime_config() -> None:
    runtime_config = RuntimeConfig(
        recovery_max_age_days=4,
        training_max_age_days=9,
    )

    builder = ContextBuilder(
        FakeClient(),
        garmin_archive=FakeArchive(),
        runtime_config=runtime_config,
        recovery_max_age_days=2,
        training_max_age_days=6,
    )

    assert builder.runtime_config is runtime_config
    assert builder.recovery_max_age_days == 2
    assert builder.training_max_age_days == 6


def test_invalid_explicit_thresholds_use_runtime_config() -> None:
    runtime_config = RuntimeConfig(
        recovery_max_age_days=4,
        training_max_age_days=9,
    )

    builder = ContextBuilder(
        FakeClient(),
        garmin_archive=FakeArchive(),
        runtime_config=runtime_config,
        recovery_max_age_days=-1,
        training_max_age_days="non-numerico",
    )

    assert builder.recovery_max_age_days == 4
    assert builder.training_max_age_days == 9