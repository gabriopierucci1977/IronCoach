from copy import deepcopy
from datetime import datetime, timezone
import sys

import pytest

from backend.maintain_plan.models import Composition, Discipline
from backend.maintain_plan.runtime_actual_session_adapter import (
    RuntimeActivityValidationError, UnsupportedRuntimeActivity,
    build_actual_session, runtime_actual_session_id,
)
from backend.maintain_plan.serialization import serialize_contract


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


@pytest.mark.parametrize("kind", ["Running", " running", "foo_running", "triathlon"])
def test_unsupported_classification(kind):
    value = activity()
    value["raw"]["activity_type"] = kind
    with pytest.raises(UnsupportedRuntimeActivity):
        build_actual_session(value, "athlete", normalized_at=NOW)


@pytest.mark.parametrize("kind", [None, 1, [], {}, True, ""])
def test_structurally_invalid_activity_type_is_a_validation_error(kind):
    value = activity()
    value["raw"]["activity_type"] = kind
    with pytest.raises(RuntimeActivityValidationError):
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


@pytest.mark.parametrize(("duration", "expected"), [
    (30, 30),
    (0, 0),
    (None, None),
])
def test_top_level_duration_does_not_require_raw_duplication(duration, expected):
    value = activity()
    value["duration_minutes"] = duration
    assert "duration_minutes" not in value["raw"]

    result = build_actual_session(value, "athlete", normalized_at=NOW)

    metrics = {item["metric"]: item["value"]
               for item in result.components[0].secondary_metrics}
    assert metrics.get("duration") == expected
    assert ("duration" in metrics) is (expected is not None)


def test_absent_top_level_duration_remains_missing():
    value = activity()
    value.pop("duration_minutes")
    result = build_actual_session(value, "athlete", normalized_at=NOW)
    assert all(item["metric"] != "duration"
               for item in result.components[0].secondary_metrics)


@pytest.mark.parametrize("invalid", [True, "30", float("nan"), float("inf"), -1])
@pytest.mark.parametrize("location", ["top-level", "raw"])
def test_invalid_duration_is_rejected_at_either_projection_level(location, invalid):
    value = activity()
    value["raw"]["duration_minutes"] = 30
    if location == "top-level":
        value["duration_minutes"] = invalid
    else:
        value["raw"]["duration_minutes"] = invalid
    with pytest.raises(RuntimeActivityValidationError, match="duration_minutes"):
        build_actual_session(value, "athlete", normalized_at=NOW)


class NonNumeric:
    pass


@pytest.mark.parametrize("kind", ["running", "strength_training"])
@pytest.mark.parametrize("invalid", [
    10**10000, -(10**10000), int(sys.float_info.max) + 1,
    float("nan"), float("inf"), float("-inf"), True, False, "30", {}, [],
    NonNumeric(),
], ids=[
    "huge-positive", "huge-negative", "above-float-max", "nan", "positive-inf",
    "negative-inf", "true", "false", "numeric-string", "dict", "list", "object",
])
def test_all_invalid_numeric_shapes_are_validation_errors_before_classification(
        kind, invalid):
    value = activity(kind)
    value["raw"]["duration_minutes"] = invalid

    with pytest.raises(RuntimeActivityValidationError, match="duration_minutes"):
        build_actual_session(value, "athlete", normalized_at=NOW)


@pytest.mark.parametrize("kind", ["running", "strength_training"])
@pytest.mark.parametrize("location", [
    "duration_minutes", "raw.duration_minutes", "distance_km",
    "raw.distance_km", "heart_rate.average", "power.average",
])
@pytest.mark.parametrize("invalid", [10**10000, -(10**10000)],
                         ids=["huge-positive", "huge-negative"])
def test_oversized_numbers_are_rejected_at_every_numeric_boundary(
        kind, location, invalid):
    value = activity(kind)
    target = value
    parts = location.split(".")
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = invalid

    with pytest.raises(RuntimeActivityValidationError):
        build_actual_session(value, "athlete", normalized_at=NOW)


def test_maximum_finite_float_is_preserved():
    value = activity()
    value["duration_minutes"] = sys.float_info.max

    result = build_actual_session(value, "athlete", normalized_at=NOW)

    duration = next(metric for metric in result.components[0].secondary_metrics
                    if metric["metric"] == "duration")
    assert duration["value"] == sys.float_info.max


@pytest.mark.parametrize("segments", [
    [{"sport": "BIKE"}], [{"sport": "bike"}],
    [{"activity_type": "strength_training"}], [{}],
    [{"sport": "RUN", "activity_type": "road_biking"}],
])
def test_adversarial_segment_classifications_are_unsupported(segments):
    value = activity()
    value["segments"] = segments
    with pytest.raises(UnsupportedRuntimeActivity):
        build_actual_session(value, "athlete", normalized_at=NOW)


def test_homogeneous_segments_are_preserved_as_evidence():
    value = activity()
    value["segments"] = [{"sport": "RUN"}, {"activity_type": "running"}]
    result = build_actual_session(value, "athlete", normalized_at=NOW)
    assert [dict(item) for item in result.source_activities[0].provenance["segments"]] == value["segments"]


def test_malformed_segment_is_a_technical_error():
    value = activity()
    value["segments"] = ["RUN"]
    with pytest.raises(RuntimeActivityValidationError):
        build_actual_session(value, "athlete", normalized_at=NOW)


@pytest.mark.parametrize(("field", "invalid"), [
    ("sport", 1), ("sport", []), ("sport", None), ("sport", True),
    ("sport", ""), ("activity_type", 1), ("activity_type", []),
    ("activity_type", {}), ("activity_type", None),
])
def test_structurally_invalid_segment_classifier_is_a_validation_error(field, invalid):
    value = activity()
    value["segments"] = [{field: invalid}]
    with pytest.raises(RuntimeActivityValidationError):
        build_actual_session(value, "athlete", normalized_at=NOW)


def test_all_segment_classifiers_are_validated_before_comparison():
    value = activity()
    value["segments"] = [{"sport": "BIKE", "activity_type": []}]
    with pytest.raises(RuntimeActivityValidationError):
        build_actual_session(value, "athlete", normalized_at=NOW)


@pytest.mark.parametrize(("field", "value"), [
    ("activity_id", None), ("date", None), ("date", "bad"),
    ("date", "2026-09-15T08:00:00"), ("duration_minutes", "30"),
    ("heart_rate", []),
])
def test_structural_failures_raise_stable_validation_error(field, value):
    candidate = activity()
    candidate[field] = value
    with pytest.raises(RuntimeActivityValidationError):
        build_actual_session(candidate, "athlete", normalized_at=NOW)


def _set_raw_duration(candidate):
    candidate["raw"]["duration_minutes"] = {}


def _set_segment_classifier(candidate):
    candidate["segments"] = [{"sport": 1}]


@pytest.mark.parametrize("make_invalid", [
    lambda value: value.__setitem__("duration_minutes", {}),
    _set_raw_duration,
    lambda value: value.__setitem__("duration_minutes", True),
    lambda value: value.__setitem__("duration_minutes", float("nan")),
    lambda value: value.__setitem__("distance_km", {}),
    lambda value: value["raw"].__setitem__("distance_km", {}),
    lambda value: value.__setitem__("heart_rate", []),
    lambda value: value.__setitem__("power", "invalid"),
    lambda value: value.__setitem__("metadata", []),
    lambda value: value.__setitem__("segments", {}),
    lambda value: value.__setitem__("segments", ["running"]),
    _set_segment_classifier,
    lambda value: value.__setitem__("activity_id", []),
    lambda value: value.__setitem__("date", "2026-09-15T08:00:00"),
], ids=[
    "top-level-duration-object", "raw-duration-object", "duration-bool",
    "duration-nan", "distance-object", "raw-distance-object",
    "heart-rate-not-object", "power-not-object", "metadata-not-object",
    "segments-not-list", "segment-not-object", "segment-classifier-not-string",
    "activity-id-not-string", "naive-timestamp",
])
def test_structural_validation_precedes_unsupported_classification(make_invalid):
    candidate = activity("strength_training")
    make_invalid(candidate)

    with pytest.raises(RuntimeActivityValidationError):
        build_actual_session(candidate, "athlete", normalized_at=NOW)


def test_well_formed_unsupported_activity_remains_unsupported():
    with pytest.raises(UnsupportedRuntimeActivity):
        build_actual_session(activity("strength_training"), "athlete",
                             normalized_at=NOW)


@pytest.mark.parametrize("kind", ["running", "strength_training"])
@pytest.mark.parametrize("mutate", [
    lambda value: value["metadata"].__setitem__("note", "\ud800"),
    lambda value: value["metadata"].__setitem__("\ud800", "note"),
    lambda value: value.__setitem__("segments", [{"sport": "RUN", "note": "\ud800"}]),
    lambda value: value.__setitem__("segments", [{"sport": "RUN", "\ud800": "note"}]),
    lambda value: value.__setitem__("activity_id", "garmin:\ud800"),
    lambda value: value.__setitem__("source_id", "source:\ud800"),
    lambda value: value.__setitem__("file_hash", "hash:\ud800"),
], ids=[
    "metadata-value", "metadata-key", "segment-value", "segment-key",
    "activity-id", "source-id", "file-hash",
])
def test_isolated_surrogates_fail_before_classification(kind, mutate):
    candidate = activity(kind)
    mutate(candidate)

    with pytest.raises(RuntimeActivityValidationError, match="invalid Unicode"):
        build_actual_session(candidate, "athlete", normalized_at=NOW)


def test_valid_unicode_including_emoji_is_preserved():
    candidate = activity()
    candidate["activity_id"] = "garmin:🏃"
    candidate["source_id"] = "orologio:⌚"
    candidate["file_hash"] = "hash:🔒"
    candidate["metadata"] = {"emoji-😀": {"nota": "allenamento 🏃‍♀️"}}
    candidate["segments"] = [{"sport": "RUN", "nota": "veloce 🚀"}]

    result = build_actual_session(candidate, "atleta:🧑", normalized_at=NOW)

    assert result.source_activities[0].original_activity_id == "garmin:🏃"
    assert result.source_activities[0].provenance["metadata"]["emoji-😀"]["nota"] == (
        "allenamento 🏃‍♀️"
    )


class Arbitrary:
    pass


@pytest.mark.parametrize("kind", ["running", "strength_training"])
@pytest.mark.parametrize("mutate", [
    lambda value: value.__setitem__("metadata", {"bad": Arbitrary()}),
    lambda value: value.__setitem__("metadata", {"nested": [{"bad": Arbitrary()}]}),
    lambda value: value.__setitem__("metadata", {"nested": [float("nan")]}),
    lambda value: value.__setitem__("metadata", {"nested": [float("inf")]}),
    lambda value: value.__setitem__("metadata", {1: "bad"}),
    lambda value: value.__setitem__("segments", [{"sport": "RUN", "bad": Arbitrary()}]),
    lambda value: value.__setitem__("segments", [{"sport": "RUN", "nested": [{"bad": Arbitrary()}]}]),
    lambda value: value.__setitem__("source_id", 1),
    lambda value: value.__setitem__("source_id", ""),
    lambda value: value.__setitem__("file_hash", []),
    lambda value: value.__setitem__("file_hash", ""),
], ids=[
    "metadata-object", "metadata-nested-object", "metadata-nan", "metadata-infinity",
    "metadata-key", "segment-object", "segment-nested-object", "source-id-type",
    "source-id-empty", "file-hash-type", "file-hash-empty",
])
def test_copied_subtrees_are_validated_before_classification(kind, mutate):
    candidate = activity(kind)
    mutate(candidate)
    with pytest.raises(RuntimeActivityValidationError):
        build_actual_session(candidate, "athlete", normalized_at=NOW)


@pytest.mark.parametrize("invalid", [
    b"bytes", bytearray(b"bytes"), {"set"}, frozenset({"set"}),
    (item for item in (1,)), lambda: None, 10**10000,
], ids=["bytes", "bytearray", "set", "frozenset", "generator", "callable",
        "oversized-integer"])
def test_non_json_evidence_values_are_rejected(invalid):
    candidate = activity()
    candidate["metadata"] = {"nested": [invalid]}
    with pytest.raises(RuntimeActivityValidationError):
        build_actual_session(candidate, "athlete", normalized_at=NOW)


def test_recursive_and_pathologically_nested_evidence_is_rejected():
    cyclic = {}
    cyclic["self"] = cyclic
    candidate = activity()
    candidate["metadata"] = cyclic
    with pytest.raises(RuntimeActivityValidationError, match="recursive"):
        build_actual_session(candidate, "athlete", normalized_at=NOW)

    nested = leaf = {}
    for _ in range(101):
        child = {}
        leaf["child"] = child
        leaf = child
    candidate["metadata"] = nested
    with pytest.raises(RuntimeActivityValidationError, match="deeply"):
        build_actual_session(candidate, "athlete", normalized_at=NOW)


def test_deep_valid_evidence_is_preserved_and_codec_serializable():
    nested = leaf = {}
    for index in range(50):
        child = {"values": [None, True, index, 1.5, ("tuple",)]}
        leaf["child"] = child
        leaf = child
    candidate = activity()
    candidate["metadata"] = nested
    candidate["segments"] = [{"sport": "RUN", "details": nested}]
    candidate["source_id"] = "source-1"
    candidate["file_hash"] = "sha256:value"

    session = build_actual_session(candidate, "athlete", normalized_at=NOW,
                                   captured_at=NOW)

    assert '"payload_schema_version":"maintain-plan-json/1"' in serialize_contract(session)
