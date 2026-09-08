"""Synthetic contract tests for immutable feedback and conflict lifecycles."""

import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.maintain_plan.lifecycle_service import (
    CONFLICT_EVENT_SCHEMA, CONFLICT_LOG_SCHEMA, FEEDBACK_EVENT_SCHEMA,
    FEEDBACK_LOG_SCHEMA, project_feedback, project_source_conflict,
    source_conflict_projection_hash, source_conflict_projection_preimage,
    validate_feedback_payload, validate_source_conflict_projection,
)
from backend.maintain_plan.models import (
    ActualSessionRef, ConflictResolutionEventType, FeedbackEvent, FeedbackEventLog,
    FeedbackEventType, FeedbackLogRef, FeedbackProjectionStatus, FeedbackRef,
    ResolutionLogRef, SourceConflictProjectionStatus, SourceConflictRef,
    SourceConflictResolutionEvent, SourceConflictResolutionLog,
)
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.serialization import serialize_contract
from tests.maintain_plan.fixtures import NOW, RUN_SESSION


BASELINE = {
    "feedback_id": "feedback-1",
    "schema_version": "maintain-plan-subjective-feedback/1.0.0-draft",
    "payload_hash": "a" * 64,
    "rpe": 5,
    "pain": None,
    "unusual_fatigue": "NONE",
    "interruption": False,
    "reason": None,
    "note": "initial",
    "captured_at": NOW.isoformat(),
    "provenance": {"source": "athlete"},
    "missing_fields": [],
    "warnings": [],
}
CONFLICT = {
    "conflict_id": "conflict-1",
    "session_id": "session-1",
    "schema_version": "maintain-plan-source-conflict/1.0.0-draft",
    "field_path": "components[0].duration",
    "values": ({"value": 10, "source": "garmin"}, {"value": 12, "source": "strava"}),
}


def feedback_log():
    return FeedbackEventLog("feedback-log-1", FEEDBACK_LOG_SCHEMA,
                            FeedbackRef("session-1", "feedback-1"), ActualSessionRef("session-1"))


def feedback_event(identifier, sequence, kind, previous=None, payload=None):
    return FeedbackEvent(
        identifier, FeedbackLogRef("feedback-log-1", "session-1", "feedback-1"),
        FeedbackRef("session-1", "feedback-1"), ActualSessionRef("session-1"), kind,
        BASELINE["schema_version"], BASELINE["payload_hash"], sequence, sequence, NOW,
        "athlete", {"source": "athlete"}, FEEDBACK_EVENT_SCHEMA, previous,
        previous if kind is FeedbackEventType.CORRECTED else None, payload,
        "athlete-request" if kind is FeedbackEventType.DELETED else None, {}, (), (),
    )


def resolution_log():
    return SourceConflictResolutionLog(
        "resolution-log-1", CONFLICT_LOG_SCHEMA,
        SourceConflictRef("session-1", "conflict-1"), ActualSessionRef("session-1"))


def resolution_event(identifier, sequence, kind, previous=None, *, value=None,
                     source=None, withdrawn=None):
    return SourceConflictResolutionEvent(
        identifier, ResolutionLogRef("resolution-log-1", "conflict-1", "session-1"),
        "resolution-log-1", "conflict-1", ActualSessionRef("session-1"), sequence, kind,
        value, source, kind is ConflictResolutionEventType.UNKNOWN_ANSWER, "athlete", NOW,
        {"source": "athlete"}, CONFLICT_EVENT_SCHEMA, previous, withdrawn, {},
    )


def conflict_projection(events, version="1"):
    return project_source_conflict(
        projection_id=f"conflict-projection-{version}", projection_version=version,
        log=resolution_log(), source_conflict=CONFLICT, events=events,
        provenance={"projector": "test"}, computed_at=NOW)


def test_feedback_capture_corrections_delete_and_old_projection_is_immutable():
    captured = feedback_event("f1", 1, FeedbackEventType.CAPTURED)
    first = project_feedback(projection_id="p1", projection_version="1", log=feedback_log(),
                             baseline=BASELINE, events=(captured,), provenance={})
    corrected_payload = dict(BASELINE, rpe=7, note="corrected")
    corrected = feedback_event("f2", 2, FeedbackEventType.CORRECTED, "f1", corrected_payload)
    second = project_feedback(projection_id="p2", projection_version="2", log=feedback_log(),
                              baseline=BASELINE, events=(captured, corrected), provenance={})
    deleted = feedback_event("f3", 3, FeedbackEventType.DELETED, "f2")
    third = project_feedback(projection_id="p3", projection_version="3", log=feedback_log(),
                             baseline=BASELINE, events=(captured, corrected, deleted), provenance={})
    assert first.status is FeedbackProjectionStatus.ACTIVE and first.projected_payload["rpe"] == 5
    assert second.projected_payload["rpe"] == 7
    assert third.status is FeedbackProjectionStatus.DELETED and third.projected_payload is None
    assert first.projected_payload["rpe"] == 5


@pytest.mark.parametrize("events,baseline", [
    ((), BASELINE),
    ((feedback_event("f2", 1, FeedbackEventType.CORRECTED, payload=BASELINE),), BASELINE),
    ((feedback_event("f1", 1, FeedbackEventType.CAPTURED),
      feedback_event("f2", 3, FeedbackEventType.CORRECTED, "bad", BASELINE)), BASELINE),
    ((feedback_event("f1", 1, FeedbackEventType.CAPTURED),
      feedback_event("f2", 2, FeedbackEventType.CAPTURED, "f1")), BASELINE),
    ((feedback_event("f1", 1, FeedbackEventType.CAPTURED),), None),
])
def test_feedback_incoherent_streams_are_invalid(events, baseline):
    value = project_feedback(projection_id="p", projection_version="1", log=feedback_log(),
                             baseline=baseline, events=events, provenance={})
    assert value.status is FeedbackProjectionStatus.INVALID
    assert value.projected_payload is None and value.warnings


def test_conflict_state_machine_all_normative_transitions_and_no_selection_reuse():
    initial = conflict_projection(())
    resolved = resolution_event("r1", 1, ConflictResolutionEventType.RESOLVED,
                                value=10, source="garmin")
    unknown = resolution_event("u1", 1, ConflictResolutionEventType.UNKNOWN_ANSWER)
    withdrawn = resolution_event("r2", 2, ConflictResolutionEventType.RESOLUTION_WITHDRAWN,
                                 "r1", withdrawn="r1")
    again = resolution_event("r3", 3, ConflictResolutionEventType.RESOLVED, "r2",
                             value=12, source="strava")
    assert initial.status is SourceConflictProjectionStatus.UNRESOLVED
    assert conflict_projection((resolved,), "2").status is SourceConflictProjectionStatus.RESOLVED
    dont_know = conflict_projection((unknown,), "3")
    assert dont_know.status is SourceConflictProjectionStatus.DONT_KNOW
    after_withdrawal = conflict_projection((resolved, withdrawn), "4")
    assert after_withdrawal.status is SourceConflictProjectionStatus.UNRESOLVED
    assert after_withdrawal.selected_value is after_withdrawal.selected_source is None
    assert after_withdrawal.through_event_id == "r2" and after_withdrawal.projection_version == "4"
    assert conflict_projection((resolved, withdrawn, again), "5").selected_value == 12


@pytest.mark.parametrize("events", [
    (resolution_event("w1", 1, ConflictResolutionEventType.RESOLUTION_WITHDRAWN,
                      withdrawn="missing"),),
    (resolution_event("r1", 2, ConflictResolutionEventType.RESOLVED,
                      value=1, source="garmin"),),
    (resolution_event("r1", 1, ConflictResolutionEventType.RESOLVED,
                      value=1, source="garmin"),
     resolution_event("r2", 2, ConflictResolutionEventType.RESOLVED, "wrong",
                      value=2, source="strava")),
])
def test_conflict_invalid_stream_never_reuses_selection(events):
    value = conflict_projection(events)
    assert value.status is SourceConflictProjectionStatus.INVALID
    assert value.selected_value is value.selected_source is None and value.warnings


def test_projection_hash_policy_is_reproducible_non_self_referential_and_sensitive():
    resolved = resolution_event("r1", 1, ConflictResolutionEventType.RESOLVED,
                                value={"b": 2, "a": 1}, source="garmin")
    value = conflict_projection((resolved,))
    reordered = conflict_projection((replace(resolved, selected_value={"a": 1, "b": 2}),))
    assert value.projection_hash == reordered.projection_hash
    assert len(value.projection_hash) == 64 and value.projection_hash == value.projection_hash.lower()
    assert "projection_hash" not in json.loads(source_conflict_projection_preimage(value))
    assert source_conflict_projection_hash(replace(value, projection_hash="tampered")) == value.projection_hash
    assert source_conflict_projection_hash(replace(value, projection_version="different")) != value.projection_hash
    assert validate_source_conflict_projection(value) == ()
    assert validate_source_conflict_projection(replace(value, projection_hash="0" * 64))


def test_repository_round_trip_append_only_and_tamper_detection(tmp_path):
    path = tmp_path / "lifecycle.db"
    session = replace(RUN_SESSION, athlete_feedback=BASELINE, source_conflicts=(CONFLICT,))
    repository = MaintainPlanRepository(path)
    repository.create_actual_session(session)
    repository.create_feedback_log(feedback_log())
    captured = feedback_event("f1", 1, FeedbackEventType.CAPTURED)
    repository.append_feedback_event(captured)
    fp = project_feedback(projection_id="fp1", projection_version="1", log=feedback_log(),
                          baseline=BASELINE, events=(captured,), provenance={})
    repository.create_feedback_projection(fp)
    repository.create_source_conflict("session-1", CONFLICT)
    repository.create_resolution_log(resolution_log())
    resolved = resolution_event("r1", 1, ConflictResolutionEventType.RESOLVED,
                                value=10, source="garmin")
    repository.append_resolution_event(resolved)
    cp = conflict_projection((resolved,))
    repository.create_source_conflict_projection(cp)
    reopened = MaintainPlanRepository(path)
    assert reopened.list_feedback_events("feedback-log-1") == (captured,)
    assert reopened.get_feedback_projection("fp1") == fp
    assert reopened.list_resolution_events("resolution-log-1") == (resolved,)
    assert reopened.get_source_conflict_projection(cp.projection_id) == cp
    with pytest.raises((sqlite3.IntegrityError, ValueError)):
        reopened.append_feedback_event(captured)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE maintain_plan_source_conflict_projections SET projection_hash = ?",
                           ("0" * 64,))
    with pytest.raises(ValueError, match="metadata does not match"):
        reopened.get_source_conflict_projection(cp.projection_id)


def test_append_rejects_gap_before_writing(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "atomic.db")
    repository.create_actual_session(replace(RUN_SESSION, athlete_feedback=BASELINE))
    repository.create_feedback_log(feedback_log())
    with pytest.raises(ValueError):
        repository.append_feedback_event(feedback_event("f2", 2, FeedbackEventType.CORRECTED,
                                                        "f1", BASELINE))
    assert repository.list_feedback_events("feedback-log-1") == ()


@pytest.mark.parametrize("change", [
    {"session_id": "session-2"},
    {"field_path": "components[1].duration"},
    {"values": ({"value": 99, "source": "garmin"}, {"value": 12, "source": "strava"})},
    {"values": ({"value": 10, "source": "other"}, {"value": 12, "source": "strava"})},
    {"provenance": {"source": "changed"}},
    {"captured_at": NOW.isoformat()},
    {"policy_id": "changed"},
    {"missing_fields": ("values",)},
    {"warnings": ("changed",)},
])
def test_source_conflict_same_id_but_different_structure_is_rejected_without_write(tmp_path, change):
    canonical = dict(CONFLICT, provenance={"source": "normalizer"}, captured_at=NOW,
                     policy_id="maintain-plan-source-conflicts", policy_version="1.0.0-draft",
                     missing_fields=(), warnings=())
    repository = MaintainPlanRepository(tmp_path / "conflict.db")
    repository.create_actual_session(replace(RUN_SESSION, source_conflicts=(canonical,)))
    with pytest.raises(ValueError, match="resolve exactly"):
        repository.create_source_conflict("session-1", dict(canonical, **change))
    assert repository.get_source_conflict("session-1", "conflict-1") is None


def test_source_conflict_equivalent_containers_persist_canonical_session_value(tmp_path):
    canonical = dict(CONFLICT, values=tuple(CONFLICT["values"]), missing_fields=(), warnings=())
    supplied = dict(canonical, values=list(CONFLICT["values"]), missing_fields=[], warnings=[])
    repository = MaintainPlanRepository(tmp_path / "equivalent.db")
    repository.create_actual_session(replace(RUN_SESSION, source_conflicts=(canonical,)))
    repository.create_source_conflict("session-1", supplied)
    assert repository.get_source_conflict("session-1", "conflict-1") == canonical


def test_source_conflict_absent_or_duplicated_is_rejected(tmp_path):
    absent = MaintainPlanRepository(tmp_path / "absent.db")
    absent.create_actual_session(RUN_SESSION)
    with pytest.raises(ValueError):
        absent.create_source_conflict("session-1", CONFLICT)
    duplicate = MaintainPlanRepository(tmp_path / "duplicate.db")
    duplicate.create_actual_session(replace(RUN_SESSION, source_conflicts=(CONFLICT, CONFLICT)))
    with pytest.raises(ValueError):
        duplicate.create_source_conflict("session-1", CONFLICT)


def test_source_conflict_tampered_sqlite_payload_is_rejected_on_read(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "tampered-conflict.db")
    repository.create_actual_session(replace(RUN_SESSION, source_conflicts=(CONFLICT,)))
    repository.create_source_conflict("session-1", CONFLICT)
    altered = dict(CONFLICT, field_path="different")
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("UPDATE maintain_plan_source_conflicts SET payload_json=?",
                           (serialize_contract(altered),))
    with pytest.raises(ValueError, match="resolve exactly"):
        repository.get_source_conflict("session-1", "conflict-1")


@pytest.mark.parametrize("field,value", [
    ("feedback_id", "other"), ("schema_version", "other/1"),
    ("payload_hash", "b" * 64), ("captured_at", "2026-01-02T00:00:00+00:00"),
    ("provenance", {"source": "other"}),
])
def test_corrected_payload_cannot_change_immutable_baseline_metadata(field, value):
    assert validate_feedback_payload(dict(BASELINE, **{field: value}), baseline=BASELINE)


@pytest.mark.parametrize("field,value", [
    ("feedback_id", None), ("payload_hash", "not-a-digest"),
    ("rpe", True), ("rpe", 11), ("pain", "3"), ("unusual_fatigue", "EXTREME"),
    ("interruption", 1), ("reason", "UNKNOWN"), ("note", 10),
    ("captured_at", "2026-01-01T08:00:00"), ("provenance", []),
    ("provenance", {"source": {"unsupported": object()}}),
    ("missing_fields", [1]), ("warnings", ["duplicate", "duplicate"]),
])
def test_feedback_payload_rejects_invalid_types_ranges_enums_and_nested_shapes(field, value):
    assert validate_feedback_payload(dict(BASELINE, **{field: value}))


@pytest.mark.parametrize("field,value,valid", [
    ("rpe", 0, False), ("rpe", 1, True), ("rpe", 10, True), ("rpe", 11, False),
    ("pain", -1, False), ("pain", 0, True), ("pain", 10, True), ("pain", 11, False),
    ("rpe", float("nan"), False), ("rpe", float("inf"), False),
    ("pain", float("-inf"), False), ("pain", True, False),
])
def test_feedback_numeric_boundaries_are_distinct(field, value, valid):
    assert (validate_feedback_payload(dict(BASELINE, **{field: value})) == ()) is valid


@pytest.mark.parametrize("payload", [
    {key: value for key, value in BASELINE.items() if key != "note"},
    dict(BASELINE, unexpected=True),
])
def test_corrected_payload_rejects_missing_or_additional_keys(payload):
    assert validate_feedback_payload(payload, baseline=BASELINE)


def test_repository_rejects_invalid_correction_atomically_and_detects_tampering(tmp_path):
    repository = MaintainPlanRepository(tmp_path / "feedback-validation.db")
    repository.create_actual_session(replace(RUN_SESSION, athlete_feedback=BASELINE))
    repository.create_feedback_log(feedback_log())
    captured = feedback_event("f1", 1, FeedbackEventType.CAPTURED)
    repository.append_feedback_event(captured)
    invalid = feedback_event("f2", 2, FeedbackEventType.CORRECTED, "f1",
                             dict(BASELINE, feedback_id="other"))
    with pytest.raises(ValueError, match="immutable"):
        repository.append_feedback_event(invalid)
    assert repository.list_feedback_events("feedback-log-1") == (captured,)

    valid = feedback_event("f2", 2, FeedbackEventType.CORRECTED, "f1",
                           dict(BASELINE, rpe=7))
    repository.append_feedback_event(valid)
    tampered = replace(valid, corrected_payload=dict(BASELINE, pain=99))
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("UPDATE maintain_plan_feedback_events SET payload_json=? WHERE feedback_event_id='f2'",
                           (serialize_contract(tampered),))
    with pytest.raises(ValueError):
        repository.list_feedback_events("feedback-log-1")


def test_second_correction_is_always_validated_against_original_baseline():
    captured = feedback_event("f1", 1, FeedbackEventType.CAPTURED)
    first = feedback_event("f2", 2, FeedbackEventType.CORRECTED, "f1", dict(BASELINE, rpe=7))
    second = feedback_event("f3", 3, FeedbackEventType.CORRECTED, "f2",
                            dict(BASELINE, rpe=8, provenance={"source": "altered"}))
    projection = project_feedback(projection_id="p", projection_version="1", log=feedback_log(),
                                  baseline=BASELINE, events=(captured, first, second), provenance={})
    assert projection.status is FeedbackProjectionStatus.INVALID
    assert projection.projected_payload is None and projection.warnings
