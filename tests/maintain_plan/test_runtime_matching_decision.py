"""Global, pure runtime matching decision tests."""

from dataclasses import replace
from datetime import timedelta

import pytest

from backend.maintain_plan.models import DirectIdEvidence
from backend.maintain_plan.runtime_matching_decision import (
    CandidateCardinality, DecisionReason, DecisionStatus, MatchingDecisionInputError,
    decide_runtime_matching,
)
from backend.maintain_plan.runtime_matching_scope import validate_runtime_matching_scope
from tests.maintain_plan.fixtures import NOW, RUN_PRESCRIPTION, RUN_SESSION


def snapshot(identifier, *, workout_id=None, offset=0):
    return replace(
        RUN_PRESCRIPTION,
        prescription_snapshot_id=identifier,
        workout_id=workout_id or f"workout-{identifier}",
        scheduled_window=replace(
            RUN_PRESCRIPTION.scheduled_window,
            start=NOW + timedelta(hours=offset),
            end=NOW + timedelta(hours=offset + 1),
        ),
    )


def session(identifier, *, offset=0):
    return replace(RUN_SESSION, session_id=identifier, start=NOW + timedelta(hours=offset))


def evidence(identifier, session_id, target):
    return DirectIdEvidence(identifier, session_id, target, "explicit-return", {})


def decide(snapshots, sessions, direct=()):
    return decide_runtime_matching(validate_runtime_matching_scope(
        "athlete-1", snapshots, sessions, direct))


def test_requires_the_prevalidated_boundary():
    with pytest.raises(MatchingDecisionInputError):
        decide_runtime_matching(object())


def test_zero_is_not_a_skipped_session_and_has_no_mapping():
    result = decide((snapshot("p"),), ())
    assert result.status is DecisionStatus.NOT_EVALUABLE
    assert result.cardinality is CandidateCardinality.ZERO
    assert result.selected_pair is None
    assert result.reasons == (DecisionReason.NO_CANDIDATE,)


def test_one_global_pair_is_selected_without_persistence():
    result = decide((snapshot("p"),), (session("s"),))
    assert result.status is DecisionStatus.MATCHED
    assert result.cardinality is CandidateCardinality.ONE
    assert (result.selected_pair.prescription_snapshot_id,
            result.selected_pair.session_id) == ("p", "s")
    assert not hasattr(result, "prescription_mapping")


def test_multiple_sessions_for_one_prescription_are_reported_globally():
    result = decide((snapshot("p"),), (session("z"), session("a")))
    assert result.status is DecisionStatus.CONFIRMATION_REQUIRED
    assert result.cardinality is CandidateCardinality.MULTIPLE
    assert DecisionReason.PRESCRIPTION_COMPETITION in result.reasons
    assert result.involved_session_ids == ("a", "z")


def test_one_session_for_multiple_prescriptions_is_reported_globally():
    result = decide((snapshot("z"), snapshot("a")), (session("s"),))
    assert result.status is DecisionStatus.CONFIRMATION_REQUIRED
    assert result.cardinality is CandidateCardinality.MULTIPLE
    assert DecisionReason.SESSION_COMPETITION in result.reasons
    assert result.involved_prescription_ids == ("a", "z")


def test_input_order_never_selects_a_candidate():
    snapshots = (snapshot("z"), snapshot("a"))
    sessions = (session("z"), session("a"))
    first = decide(snapshots, sessions)
    second = decide(tuple(reversed(snapshots)), tuple(reversed(sessions)))
    assert first == second
    assert first.selected_pair is None
    assert len(first.pair_evaluations) == 4


def test_direct_id_uses_snapshot_identity_never_workout_id():
    prescribed = snapshot("canonical", workout_id="legacy-workout")
    dangling = decide((prescribed,), (session("s", offset=20),),
                      (evidence("e", "s", "legacy-workout"),))
    assert dangling.status is DecisionStatus.CONFIRMATION_REQUIRED
    assert dangling.cardinality is CandidateCardinality.ZERO
    assert DecisionReason.DIRECT_ID_DANGLING in dangling.reasons

    resolved = decide((prescribed,), (session("s", offset=20),),
                      (evidence("e", "s", "canonical"),))
    assert resolved.status is DecisionStatus.MATCHED
    assert resolved.selected_pair.direct is True


@pytest.mark.parametrize("target, reason", [
    (None, DecisionReason.DIRECT_ID_MISSING),
    (" ", DecisionReason.DIRECT_ID_MALFORMED),
    ("absent", DecisionReason.DIRECT_ID_DANGLING),
])
def test_uncertain_direct_id_blocks_structural_fallback(target, reason):
    result = decide((snapshot("p"),), (session("s"),), (evidence("e", "s", target),))
    assert result.status is DecisionStatus.CONFIRMATION_REQUIRED
    assert result.cardinality is CandidateCardinality.ZERO
    assert result.candidates == ()
    assert reason in result.reasons
    assert result.involved_session_ids == ("s",)


@pytest.mark.parametrize("target", [object(), ["p"], {"id": "p"}, "bad\ud800"])
def test_non_string_or_invalid_utf8_direct_id_is_non_automatic_without_type_error(target):
    result = decide((snapshot("p"),), (session("s"),), (evidence("e", "s", target),))
    assert result.status is DecisionStatus.CONFIRMATION_REQUIRED
    assert result.cardinality is CandidateCardinality.ZERO
    assert result.selected_pair is None
    assert result.candidates == ()
    assert DecisionReason.DIRECT_ID_MALFORMED in result.reasons
    assert result.involved_session_ids == ("s",)


def test_contradictory_direct_ids_expose_all_possibilities():
    result = decide(
        (snapshot("a"), snapshot("b")), (session("s"),),
        (evidence("one", "s", "a"), evidence("two", "s", "b")),
    )
    assert result.status is DecisionStatus.CONFIRMATION_REQUIRED
    assert result.cardinality is CandidateCardinality.MULTIPLE
    assert DecisionReason.DIRECT_ID_CONTRADICTORY in result.reasons
    assert {(item.prescription_snapshot_id, item.session_id) for item in result.candidates} == {
        ("a", "s"), ("b", "s")}


def test_duplicate_assertion_keeps_one_possibility_but_requires_confirmation():
    result = decide(
        (snapshot("p"),), (session("s"),),
        (evidence("one", "s", "p"), evidence("two", "s", "p")),
    )
    assert result.cardinality is CandidateCardinality.ONE
    assert result.status is DecisionStatus.CONFIRMATION_REQUIRED
    assert result.selected_pair is None
    assert DecisionReason.DIRECT_ID_DUPLICATE in result.reasons


def test_corrupt_data_is_rejected_before_decision_not_filtered():
    corrupt = replace(session("bad"), subject_ref="another-athlete")
    with pytest.raises(ValueError, match="byte-exactly"):
        decide((snapshot("p"),), (session("good"), corrupt))


def test_decision_has_no_database_dependency(monkeypatch):
    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: pytest.fail("database access"))
    assert decide((snapshot("p"),), (session("s"),)).status is DecisionStatus.MATCHED
