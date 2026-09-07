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
    validate_source_conflict_projection,
)
from backend.maintain_plan.models import (
    ActualSessionRef, ConflictResolutionEventType, FeedbackEvent, FeedbackEventLog,
    FeedbackEventType, FeedbackLogRef, FeedbackProjectionStatus, FeedbackRef,
    ResolutionLogRef, SourceConflictProjectionStatus, SourceConflictRef,
    SourceConflictResolutionEvent, SourceConflictResolutionLog,
)
from backend.maintain_plan.repository import MaintainPlanRepository
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
