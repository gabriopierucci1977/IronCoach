"""Synthetic tests for optional coach-portal RPE capture."""

from datetime import datetime, timezone
import sqlite3

import pytest

from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.rpe_feedback import (
    capture_database_observed_rpe, capture_observed_rpe, qualified_rpe,
    rpe_attribution, session_rpe, session_rpe_state,
)
from tests.maintain_plan.fixtures import RUN_SESSION


NOW = datetime(2026, 2, 3, 12, tzinfo=timezone.utc)


def repository(tmp_path, name="scenario.sqlite"):
    value = MaintainPlanRepository(tmp_path / name)
    value.create_actual_session(RUN_SESSION)
    return value


@pytest.mark.parametrize("value", ["1", "7", "10"])
def test_valid_rpe_is_attached_to_existing_session_with_truthful_provenance(tmp_path, value):
    repo = repository(tmp_path)

    projection = capture_observed_rpe(
        repo, subject_ref="athlete-1", session_id="session-1",
        submitted_rpe=value, captured_at=NOW)

    assert projection.projected_payload["rpe"] == int(value)
    assert projection.projected_payload["captured_at"] == NOW.isoformat()
    assert projection.projected_payload["provenance"] == {
        "source": "ironcoach-coach-portal",
        "declared_by": "ironcoach-user",
        "capture_method": "direct-user-declaration",
        "rpe_qualification": {
            "source": "ironcoach-user", "meaning": "session_rpe",
            "scale": "1-10", "verified": True,
        },
    }
    assert repo.get_actual_session("session-1").athlete_feedback is None
    assert repo.get_actual_session("session-1").components[0].intensity_methods == ()


@pytest.mark.parametrize("value", ["0", "11", "7.0", "garbage"])
def test_invalid_rpe_is_rejected_without_writes(tmp_path, value):
    repo = repository(tmp_path)
    with pytest.raises(ValueError, match="intero da 1 a 10"):
        capture_observed_rpe(repo, subject_ref="athlete-1", session_id="session-1",
                             submitted_rpe=value, captured_at=NOW)
    assert session_rpe(repo, "session-1") is None


def test_omitted_answer_is_persisted_as_missing_and_feedback_continues(tmp_path):
    repo = repository(tmp_path)
    projection = capture_observed_rpe(
        repo, subject_ref="athlete-1", session_id="session-1",
        submitted_rpe="", captured_at=NOW)
    assert projection.projected_payload["rpe"] is None
    assert "rpe" in projection.projected_payload["missing_fields"]
    assert projection.status.value == "ACTIVE"


def test_only_explicitly_qualified_source_value_is_reused():
    unqualified_garmin = {
        "rpe": 70,
        "provenance": {"source": "garmin", "field": "workoutRpe"},
    }
    qualified = {
        "rpe": 7,
        "provenance": {"rpe_qualification": {
            "source": "verified-fixture", "meaning": "session_rpe",
            "scale": "1-10", "verified": True,
        }},
    }
    assert qualified_rpe(unqualified_garmin) is None
    assert qualified_rpe(qualified) == 7


def test_rpe_attribution_requires_explicit_portal_declaration():
    portal = {
        "provenance": {
            "source": "ironcoach-coach-portal",
            "declared_by": "ironcoach-user",
            "capture_method": "direct-user-declaration",
            "rpe_qualification": {"source": "ironcoach-user"},
        }}
    imported = {
        "provenance": {"rpe_qualification": {"source": "verified-garmin-import"}}}
    unattributable = {
        "provenance": {"rpe_qualification": {"source": 42}}}

    assert rpe_attribution(portal) == ("PORTAL_USER", "IronCoach")
    assert rpe_attribution(imported) == ("IMPORTED_SOURCE", "verified-garmin-import")
    assert rpe_attribution(unattributable) == ("NEUTRAL", None)


def test_repeat_submission_is_idempotent_and_correction_is_append_only(tmp_path):
    repo = repository(tmp_path)
    first = capture_observed_rpe(
        repo, subject_ref="athlete-1", session_id="session-1",
        submitted_rpe="6", captured_at=NOW)
    repeated = capture_observed_rpe(
        repo, subject_ref="athlete-1", session_id="session-1",
        submitted_rpe="6", captured_at=NOW)
    assert repeated == first
    corrected = capture_observed_rpe(
        repo, subject_ref="athlete-1", session_id="session-1",
        submitted_rpe="7", captured_at=datetime(2026, 2, 4, 12, tzinfo=timezone.utc))
    assert corrected.projected_payload["rpe"] == 7
    log = repo.get_feedback_log(corrected.feedback_log_ref.feedback_log_id)
    events = repo.list_feedback_events(log.feedback_log_id)
    assert [event.event_type.value for event in events] == ["CAPTURED", "CORRECTED"]
    assert events[1].superseded_event_ref == events[0].feedback_event_id
    assert repo._feedback_baseline(log)["rpe"] == 6


def test_omission_can_be_followed_by_value_without_rewriting_baseline(tmp_path):
    repo = repository(tmp_path)
    omitted = capture_observed_rpe(
        repo, subject_ref="athlete-1", session_id="session-1",
        submitted_rpe="", captured_at=NOW)
    repeated_omission = capture_observed_rpe(
        repo, subject_ref="athlete-1", session_id="session-1",
        submitted_rpe="", captured_at=NOW)
    assert repeated_omission == omitted
    assert session_rpe_state(repo, "session-1").status == "OMITTED"
    added = capture_observed_rpe(
        repo, subject_ref="athlete-1", session_id="session-1",
        submitted_rpe="8", captured_at=datetime(2026, 2, 4, 12, tzinfo=timezone.utc))
    assert added.projected_payload["rpe"] == 8
    assert session_rpe_state(repo, "session-1").status == "VALUE"
    log = repo.get_feedback_log(added.feedback_log_ref.feedback_log_id)
    assert repo._feedback_baseline(log)["rpe"] is None
    assert omitted.baseline_payload_hash == added.baseline_payload_hash


def test_initial_capture_rolls_back_log_event_and_projection_on_interruption(tmp_path):
    repo = repository(tmp_path)
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute(
            "CREATE TRIGGER synthetic_interrupt_feedback_event BEFORE INSERT ON "
            "maintain_plan_feedback_events BEGIN SELECT RAISE(ABORT, 'synthetic interruption'); END")
    with pytest.raises(sqlite3.IntegrityError, match="synthetic interruption"):
        capture_observed_rpe(
            repo, subject_ref="athlete-1", session_id="session-1",
            submitted_rpe="5", captured_at=NOW)
    with sqlite3.connect(repo.database_path) as connection:
        assert connection.execute("SELECT count(*) FROM maintain_plan_feedback_logs").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM maintain_plan_feedback_events").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM maintain_plan_feedback_projections").fetchone() == (0,)


def test_correction_rolls_back_event_when_projection_write_is_interrupted(tmp_path):
    repo = repository(tmp_path)
    first = capture_observed_rpe(
        repo, subject_ref="athlete-1", session_id="session-1",
        submitted_rpe="5", captured_at=NOW)
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute(
            "CREATE TRIGGER synthetic_interrupt_feedback_projection BEFORE INSERT ON "
            "maintain_plan_feedback_projections WHEN NEW.projection_version = '2' "
            "BEGIN SELECT RAISE(ABORT, 'synthetic interruption'); END")
    with pytest.raises(sqlite3.IntegrityError, match="synthetic interruption"):
        capture_observed_rpe(
            repo, subject_ref="athlete-1", session_id="session-1",
            submitted_rpe="9", captured_at=datetime(2026, 2, 4, 12, tzinfo=timezone.utc))
    assert session_rpe(repo, "session-1") == 5
    events = repo.list_feedback_events(first.feedback_log_ref.feedback_log_id)
    assert len(events) == 1
    assert events[0].event_type.value == "CAPTURED"


def test_unanswered_and_explicit_omission_are_distinct_states(tmp_path):
    repo = repository(tmp_path)
    assert session_rpe_state(repo, "session-1").status == "UNANSWERED"
    capture_observed_rpe(repo, subject_ref="athlete-1", session_id="session-1",
                         submitted_rpe="", captured_at=NOW)
    assert session_rpe_state(repo, "session-1").status == "OMITTED"


def test_subject_is_derived_from_persisted_session_and_scenarios_are_isolated(tmp_path):
    first = repository(tmp_path, "first.sqlite")
    second = repository(tmp_path, "second.sqlite")
    with pytest.raises(ValueError, match="soggetto configurato"):
        capture_observed_rpe(first, subject_ref="arbitrary-athlete", session_id="session-1",
                             submitted_rpe="5", captured_at=NOW)
    capture_observed_rpe(first, subject_ref="athlete-1", session_id="session-1",
                         submitted_rpe="5", captured_at=NOW)
    assert session_rpe(first, "session-1") == 5
    assert session_rpe(second, "session-1") is None


def test_database_boundary_discards_form_identity(tmp_path):
    repo = repository(tmp_path)
    capture_database_observed_rpe(
        str(repo.database_path), subject_ref="form-controlled-identity",
        session_id="session-1", submitted_rpe="4", captured_at=NOW)
    assert session_rpe(repo, "session-1") == 4
