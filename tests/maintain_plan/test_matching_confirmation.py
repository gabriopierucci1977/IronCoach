"""Synthetic coverage for deterministic matching and immutable confirmation."""

from dataclasses import replace
from datetime import timedelta
import sqlite3

import pytest

from backend.maintain_plan.confirmation_service import answer_confirmation, request_confirmation
from backend.maintain_plan.matching_service import match
from backend.maintain_plan.models import (ActualSession, Composition, ConfirmationAnswerType,
    ConfirmationStatus, DirectIdEvidence, Discipline, MatchingStatus, ObservedComponent,
    ObservedTransition)
from backend.maintain_plan.repository import MaintainPlanRepository
from tests.maintain_plan.fixtures import (BRICK_PRESCRIPTION, NOW, RUN_PRESCRIPTION,
                                          RUN_SESSION, observed)


def _session(identifier, start=NOW, discipline=Discipline.RUN, **changes):
    return replace(RUN_SESSION, session_id=identifier, start=start,
                   components=(observed(f"{identifier}-component", 0, discipline),), **changes)


def _match(snapshot, sessions, evidence=()):
    return match(snapshot, tuple(sessions), matching_result_id="result-1", mapping_id="mapping-1",
                 created_at=NOW, direct_id_evidence=tuple(evidence), provenance={"source": "test"})


def test_direct_id_is_absolute_and_ambiguous_direct_id_has_no_fallback():
    wrong_execution = _session("different", start=NOW + timedelta(days=20), discipline=Discipline.SWIM)
    evidence = DirectIdEvidence("e1", "different", "workout-1", "device", {})
    result = _match(RUN_PRESCRIPTION, (wrong_execution,), (evidence,))
    assert result.status is MatchingStatus.MATCHED
    assert result.prescription_mapping.actual_session_ref == "different"

    other = _session("other")
    ambiguous = _match(RUN_PRESCRIPTION, (wrong_execution, other), (
        evidence, DirectIdEvidence("e2", "other", "workout-1", "device", {})))
    assert ambiguous.status is MatchingStatus.CONFIRMATION_REQUIRED
    assert ambiguous.candidate_set == ()
    assert ambiguous.prescription_mapping is None


@pytest.mark.parametrize("start,matched", [
    (NOW - timedelta(microseconds=1), False), (NOW, True),
    (NOW + timedelta(microseconds=1), False),
])
def test_scheduled_window_boundaries_are_inclusive(start, matched):
    result = _match(RUN_PRESCRIPTION, (_session("s", start=start),))
    assert (result.status is MatchingStatus.MATCHED) is matched


def test_candidate_cardinality_is_deterministic_and_context_does_not_filter():
    indoor = replace(_session("z"), components=(replace(observed("c", 0, Discipline.RUN),
                                                       environment=None, mode=None),))
    other = _session("a")
    result = _match(RUN_PRESCRIPTION, (indoor, other))
    assert result.status is MatchingStatus.CONFIRMATION_REQUIRED
    assert result.candidate_set == ("a", "z")
    assert result.prescription_mapping is None


def test_brick_requires_order_timing_transition_and_declared_gap():
    first = ObservedComponent("run", 0, Discipline.RUN, start=NOW, end=NOW + timedelta(minutes=30))
    second = ObservedComponent("bike", 1, Discipline.BIKE,
                               start=NOW + timedelta(minutes=40), end=NOW + timedelta(minutes=90))
    session = ActualSession("brick", NOW, Composition.BRICK, (first, second), transition_ids=("t",), transitions=(
        ObservedTransition("t", "run", "bike", duration_minutes=10),))
    assert _match(BRICK_PRESCRIPTION, (session,)).status is MatchingStatus.MATCHED
    too_late = replace(session, components=(first, replace(second, start=NOW + timedelta(minutes=46))), transition_ids=("t2",),
                       transitions=(ObservedTransition("t2", "run", "bike", duration_minutes=16),))
    assert _match(BRICK_PRESCRIPTION, (too_late,)).status is MatchingStatus.CONFIRMATION_REQUIRED
    overlap = replace(session, components=(first, replace(second, start=NOW + timedelta(minutes=20))))
    assert _match(BRICK_PRESCRIPTION, (overlap,)).status is MatchingStatus.CONFIRMATION_REQUIRED
    no_policy = replace(BRICK_PRESCRIPTION, brick_policy=replace(BRICK_PRESCRIPTION.brick_policy,
                                                                 policy_id=None, policy_version=None))
    assert _match(no_policy, (session,)).status is MatchingStatus.NOT_EVALUABLE


def test_confirmation_creates_new_result_without_mutating_prior_objects():
    sessions = (_session("one"), _session("two"))
    original = _match(RUN_PRESCRIPTION, sessions)
    request = request_confirmation(original, confirmation_id="question", asked_at=NOW,
                                   provenance={"source": "test"})
    answered, resolved = answer_confirmation(
        request, original, RUN_PRESCRIPTION, sessions, confirmation_id="answer",
        matching_result_id="result-2", mapping_id="mapping-2",
        answer_type=ConfirmationAnswerType.SELECT_CANDIDATE, selected_session_ref="two",
        actor="athlete", answered_at=NOW + timedelta(minutes=1), provenance={"source": "test"})
    assert request.status is ConfirmationStatus.REQUIRED
    assert original.prescription_mapping is None
    assert answered.status is ConfirmationStatus.ANSWERED
    assert resolved.status is MatchingStatus.MATCHED
    assert resolved.prescription_mapping.confirmation_ref == "answer"
    with pytest.raises(ValueError):
        answer_confirmation(request, original, RUN_PRESCRIPTION, sessions,
            confirmation_id="bad", matching_result_id="bad-result", mapping_id="bad-map",
            answer_type=ConfirmationAnswerType.SELECT_CANDIDATE, selected_session_ref="outside",
            actor="athlete", answered_at=NOW, provenance={})


def test_dont_know_keeps_mapping_null_and_confirmation_round_trips_insert_only(tmp_path):
    sessions = (_session("one"), _session("two"))
    original = _match(RUN_PRESCRIPTION, sessions)
    request = request_confirmation(original, confirmation_id="question", asked_at=NOW, provenance={})
    answer, unresolved = answer_confirmation(
        request, original, RUN_PRESCRIPTION, sessions, confirmation_id="answer",
        matching_result_id="result-2", mapping_id="unused",
        answer_type=ConfirmationAnswerType.DONT_KNOW, selected_session_ref=None,
        actor="athlete", answered_at=NOW, provenance={})
    assert answer.status is ConfirmationStatus.UNKNOWN_ANSWER
    assert unresolved.status is MatchingStatus.NOT_EVALUABLE
    assert unresolved.prescription_mapping is None

    repo = MaintainPlanRepository(tmp_path / "matching.db")
    repo.create_prescription_snapshot(RUN_PRESCRIPTION)
    for session in sessions:
        repo.create_actual_session(session)
    repo.create_matching_result(original)
    repo.create_confirmation(request)
    assert repo.get_confirmation("question") == request
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_confirmation(request)
    with sqlite3.connect(tmp_path / "matching.db") as connection:
        connection.execute("UPDATE maintain_plan_confirmations SET status='ANSWERED' WHERE confirmation_id='question'")
    with pytest.raises(ValueError):
        repo.get_confirmation("question")
