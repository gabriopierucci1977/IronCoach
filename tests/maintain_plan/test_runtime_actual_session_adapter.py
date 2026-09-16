from copy import deepcopy
from datetime import datetime, timezone

import pytest

from backend.maintain_plan.models import Composition, Discipline
from backend.maintain_plan.runtime_actual_session_adapter import (
    UnsupportedRuntimeActivity, build_actual_session, runtime_actual_session_id,
)


NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)


def activity(kind="running", sport="RUN"):
    return {"activity_id": "garmin:1", "date": "2026-09-15T08:00:00Z",
            "sport": sport, "duration_minutes": 30, "distance_km": 5,
            "heart_rate": {"average": 140, "max": 160}, "power": {},
            "segments": [], "metadata": {"device": "watch"},
            "raw": {"activity_type": kind, "distance_km": 5}}


@pytest.mark.parametrize(("kind", "sport", "discipline"), [
    ("running", "RUN", Discipline.RUN), ("road_biking", "BIKE", Discipline.BIKE),
    ("lap_swimming", "SWIM", Discipline.SWIM),
])
def test_closed_mapping(kind, sport, discipline):
    result = build_actual_session(activity(kind, sport), "athlete", normalized_at=NOW)
    assert result.composition is Composition.SINGLE
    assert result.components[0].discipline is discipline


@pytest.mark.parametrize("kind", [None, 1, "Running", " running", "foo_running", "triathlon"])
def test_unsupported_classification(kind):
    value = activity()
    value["raw"]["activity_type"] = kind
    with pytest.raises(UnsupportedRuntimeActivity):
        build_actual_session(value, "athlete", normalized_at=NOW)


def test_identity_vector_and_input_immutability():
    value = activity()
    before = deepcopy(value)
    result = build_actual_session(value, "athlete", normalized_at=NOW)
    assert value == before
    assert result.end is None
    assert runtime_actual_session_id("atleta-é", "garmin:123456789") == (
        "maintain-plan:actual-session:sha256:"
        "a7dc959a6b5773ada0993fbae272da4499a66a093d5f30632241cab4925e0559"
    )

