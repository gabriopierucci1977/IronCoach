"""Regression tests for explicit Airtable runtime training overrides."""

import json

from backend.maintain_plan.runtime_training_overrides import (
    apply_runtime_training_override,
)


def test_override_is_applied_only_to_matching_record(monkeypatch):
    monkeypatch.setenv(
        "IRONCOACH_MAINTAIN_PLAN_TRAINING_OVERRIDES",
        json.dumps(
            {
                "recBikeKeepPlan": {
                    "session_type": "continuous",
                    "intensity_method": "HR",
                    "intensity_unit": "zone",
                }
            }
        ),
    )

    selected = {
        "source_id": "recBikeKeepPlan",
        "sport": "BIKE",
        "raw": {
            "record_id": "recBikeKeepPlan",
            "Zona prevista": "Z3 Medio",
        },
    }

    other = {
        "source_id": "recOther",
        "sport": "RUN",
        "raw": {
            "record_id": "recOther",
        },
    }

    selected_result = apply_runtime_training_override(selected)
    other_result = apply_runtime_training_override(other)

    assert selected_result["session_type"] == "continuous"
    assert selected_result["intensity_method"] == "HR"
    assert selected_result["intensity_unit"] == "zone"
    assert selected_result["sport"] == "BIKE"

    assert other_result == other


def test_without_override_training_values_are_preserved(monkeypatch):
    monkeypatch.delenv(
        "IRONCOACH_MAINTAIN_PLAN_TRAINING_OVERRIDES",
        raising=False,
    )

    training = {
        "source_id": "recBikeKeepPlan",
        "sport": "BIKE",
        "raw": {
            "record_id": "recBikeKeepPlan",
            "Zona prevista": "Z3 Medio",
        },
    }

    assert apply_runtime_training_override(training) == training
