"""Synthetic coverage for deterministic matching and immutable confirmation."""

from dataclasses import replace
from datetime import timedelta
import sqlite3

import pytest

from backend.maintain_plan.confirmation_service import answer_confirmation, request_confirmation
from backend.maintain_plan.matching_service import build_mapping, match
from backend.maintain_plan.models import (ActualSession, Composition, ConfirmationAnswerType,
    ConfirmationStatus, DirectIdEvidence, Discipline, MatchStatus, MatchingStatus,
    ObservedBlock, ObservedComponent, ObservedComponentRef, ObservedRepetition,
    ObservedTransition, PlannedComponentRef, ResolutionMethod)
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.serialization import serialize_contract
from backend.maintain_plan.validators import (validate_confirmation,
    validate_execution_evaluation, validate_mapping_ownership)
from tests.maintain_plan.fixtures import (BRICK_PRESCRIPTION, NOW, RUN_PRESCRIPTION,
                                          RUN_SESSION, component_result, execution, observed)


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
    with pytest.raises(sqlite3.IntegrityError), sqlite3.connect(tmp_path / "matching.db") as connection:
        connection.execute("UPDATE maintain_plan_confirmations SET status='ANSWERED' WHERE confirmation_id='question'")
    malformed = replace(request, status=ConfirmationStatus.ANSWERED)
    with sqlite3.connect(tmp_path / "matching.db") as connection:
        connection.execute("UPDATE maintain_plan_confirmations SET payload_json=? WHERE confirmation_id='question'",
                           (serialize_contract(malformed),))
    with pytest.raises(ValueError):
        repo.get_confirmation("question")


def _observed_repetitions(count):
    return tuple(ObservedRepetition(f"rep-{index}", index, "observed-block")
                 for index in range(count))


@pytest.mark.parametrize("planned_count,observed_count,expected", [
    (6, 8, (6, 0, 2)), (8, 6, (6, 2, 0)), (6, 6, (6, 0, 0)),
    (None, 3, (0, 0, 3)),
])
def test_repetition_mapping_never_invents_or_truncates_references(
        planned_count, observed_count, expected, tmp_path):
    planned_block = replace(RUN_PRESCRIPTION.components[0].structure.blocks[0],
                            planned_repetitions=planned_count)
    component = replace(RUN_PRESCRIPTION.components[0], structure=replace(
        RUN_PRESCRIPTION.components[0].structure, blocks=(planned_block,)))
    snapshot = replace(RUN_PRESCRIPTION, components=(component,))
    observed_block = ObservedBlock("observed-block", 0,
                                   repetitions=_observed_repetitions(observed_count))
    session = replace(RUN_SESSION, components=(replace(RUN_SESSION.components[0],
                                                       blocks=(observed_block,)),))
    mapping = build_mapping(snapshot, session, mapping_id="repetitions", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    assert tuple(sum(item.match_status is status for item in mapping.repetition_mappings)
                 for status in (MatchStatus.MATCHED, MatchStatus.PLANNED_ONLY,
                                MatchStatus.OBSERVED_ONLY)) == expected
    repo = MaintainPlanRepository(tmp_path / f"repetitions-{planned_count}-{observed_count}.db")
    repo.create_prescription_snapshot(snapshot)
    repo.create_actual_session(session)
    repo.create_prescription_mapping(mapping)
    assert repo.get_prescription_mapping("repetitions") == mapping


def test_unmatched_blocks_are_preserved_and_mapping_round_trips(tmp_path):
    original = RUN_PRESCRIPTION.components[0].structure.blocks[0]
    planned_blocks = (replace(original, block_id="planned-1", block_index=0),
                      replace(original, block_id="planned-2", block_index=1))
    snapshot = replace(RUN_PRESCRIPTION, components=(replace(
        RUN_PRESCRIPTION.components[0], structure=replace(
            RUN_PRESCRIPTION.components[0].structure, blocks=planned_blocks)),))
    observed_blocks = (ObservedBlock("observed-1", 0), ObservedBlock("observed-2", 1),
                       ObservedBlock("observed-extra", 2))
    session = replace(RUN_SESSION, components=(replace(RUN_SESSION.components[0],
                                                       blocks=observed_blocks),))
    mapping = build_mapping(snapshot, session, mapping_id="blocks", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    assert [item.match_status for item in mapping.block_mappings] == [
        MatchStatus.MATCHED, MatchStatus.MATCHED, MatchStatus.OBSERVED_ONLY]
    repo = MaintainPlanRepository(tmp_path / "blocks.db")
    repo.create_prescription_snapshot(snapshot)
    repo.create_actual_session(session)
    repo.create_prescription_mapping(mapping)
    assert repo.get_prescription_mapping("blocks") == mapping


def test_planned_only_block_is_preserved():
    original = RUN_PRESCRIPTION.components[0].structure.blocks[0]
    snapshot = replace(RUN_PRESCRIPTION, components=(replace(
        RUN_PRESCRIPTION.components[0], structure=replace(
            RUN_PRESCRIPTION.components[0].structure,
            blocks=(original, replace(original, block_id="missing", block_index=1)))),))
    mapping = build_mapping(snapshot, RUN_SESSION, mapping_id="missing-block", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    assert mapping.block_mappings[-1].match_status is MatchStatus.PLANNED_ONLY
    assert mapping.block_mappings[-1].observed_block_ref is None


def test_unmatched_blocks_are_preserved_through_direct_id_and_manual_confirmation():
    original = RUN_PRESCRIPTION.components[0].structure.blocks[0]
    snapshot = replace(RUN_PRESCRIPTION, components=(replace(
        RUN_PRESCRIPTION.components[0], structure=replace(
            RUN_PRESCRIPTION.components[0].structure,
            blocks=(original, replace(original, block_id="planned-only", block_index=1)))),))
    session = replace(RUN_SESSION, session_id="block-session", start=NOW + timedelta(days=1),
                      components=(replace(RUN_SESSION.components[0],
                                          blocks=(ObservedBlock("observed", 0),)),))
    direct = match(snapshot, (session,), matching_result_id="direct", mapping_id="direct-map",
                   created_at=NOW, direct_id_evidence=(DirectIdEvidence(
                       "e", "block-session", "workout-1", "device", {}),))
    assert direct.prescription_mapping.block_mappings[-1].match_status is MatchStatus.PLANNED_ONLY
    unresolved = _match(snapshot, (session,))
    request = request_confirmation(unresolved, confirmation_id="block-question",
                                   asked_at=NOW, provenance={})
    _, resolved = answer_confirmation(
        request, unresolved, snapshot, (session,), confirmation_id="block-answer",
        matching_result_id="block-result", mapping_id="confirmed-map",
        answer_type=ConfirmationAnswerType.MANUAL_ASSOCIATION,
        selected_session_ref="block-session", actor="athlete", answered_at=NOW,
        provenance={})
    assert resolved.prescription_mapping.block_mappings[-1].match_status is MatchStatus.PLANNED_ONLY


def test_non_zero_based_component_indices_do_not_index_planned_tuple():
    first = ObservedComponent("run", 5, Discipline.RUN, start=NOW, end=NOW + timedelta(minutes=2))
    second = ObservedComponent("bike", 6, Discipline.BIKE, start=NOW + timedelta(minutes=3),
                               end=NOW + timedelta(minutes=4))
    session = ActualSession("nonzero", NOW, Composition.BRICK, (first, second),
        transition_ids=("t",), transitions=(ObservedTransition("t", "run", "bike", duration_minutes=1),))
    assert _match(BRICK_PRESCRIPTION, (session,)).status is MatchingStatus.MATCHED
    incompatible = replace(session, components=(replace(first, component_index=7), second))
    assert _match(BRICK_PRESCRIPTION, (incompatible,)).status is MatchingStatus.CONFIRMATION_REQUIRED


def test_direct_id_observed_extra_survives_downstream_planned_lookup():
    session = ActualSession("direct-extra", NOW, Composition.BRICK,
                            (observed("run", 0, Discipline.RUN), observed("extra", 1, Discipline.BIKE)))
    result = _match(RUN_PRESCRIPTION, (session,), (
        DirectIdEvidence("direct", "direct-extra", "workout-1", "device", {}),))
    assert result.prescription_mapping.component_mappings[-1].match_status is MatchStatus.OBSERVED_ONLY
    planned_result = replace(component_result("run"), observed_component_ref=ObservedComponentRef(
        "direct-extra", "run"))
    extra_result = replace(component_result("extra", match=MatchStatus.OBSERVED_ONLY),
                           observed_component_ref=ObservedComponentRef("direct-extra", "extra"))
    evaluation = execution((planned_result, extra_result), snapshot=RUN_PRESCRIPTION)
    evaluation = replace(evaluation, prescription_mapping_ref=result.prescription_mapping.mapping_id,
                         actual_session_ref="direct-extra")
    assert validate_execution_evaluation(
        evaluation, result.prescription_mapping, RUN_PRESCRIPTION, session) == ()


@pytest.mark.parametrize("mutation", [
    {"observed_component_ref": ObservedComponentRef("foreign-session", "ghost")},
    {"observed_component_ref": ObservedComponentRef("direct-extra", "ghost")},
    {"observed_component_ref": ObservedComponentRef("direct-extra", "run")},
    {"match_status": MatchStatus.MATCHED},
    {"planned_component_ref": PlannedComponentRef("snapshot-1", "run")},
])
def test_observed_only_evaluation_must_match_canonical_mapping(mutation):
    session = ActualSession("direct-extra", NOW, Composition.BRICK,
                            (observed("run", 0, Discipline.RUN), observed("extra", 1, Discipline.BIKE)))
    matching = _match(RUN_PRESCRIPTION, (session,), (
        DirectIdEvidence("direct", "direct-extra", "workout-1", "device", {}),))
    planned_result = replace(component_result("run"), observed_component_ref=ObservedComponentRef(
        "direct-extra", "run"))
    extra_result = replace(component_result("extra", match=MatchStatus.OBSERVED_ONLY),
                           observed_component_ref=ObservedComponentRef("direct-extra", "extra"))
    extra_result = replace(extra_result, **mutation)
    value = execution((planned_result, extra_result), snapshot=RUN_PRESCRIPTION)
    value = replace(value, prescription_mapping_ref=matching.prescription_mapping.mapping_id,
                    actual_session_ref="direct-extra")
    assert validate_execution_evaluation(
        value, matching.prescription_mapping, RUN_PRESCRIPTION, session)


def test_observed_only_duplicate_repository_rejection_and_tamper_detection(tmp_path):
    session = ActualSession("direct-extra", NOW, Composition.BRICK,
                            (observed("run", 0, Discipline.RUN), observed("extra", 1, Discipline.BIKE)))
    matching = _match(RUN_PRESCRIPTION, (session,), (
        DirectIdEvidence("direct", "direct-extra", "workout-1", "device", {}),))
    planned_result = replace(component_result("run"), observed_component_ref=ObservedComponentRef(
        "direct-extra", "run"))
    extra_result = replace(component_result("extra", match=MatchStatus.OBSERVED_ONLY),
                           observed_component_ref=ObservedComponentRef("direct-extra", "extra"))
    value = replace(execution((planned_result, extra_result), snapshot=RUN_PRESCRIPTION),
                    prescription_mapping_ref=matching.prescription_mapping.mapping_id,
                    actual_session_ref="direct-extra")
    repo = MaintainPlanRepository(tmp_path / "evaluation-ownership.db")
    repo.create_prescription_snapshot(RUN_PRESCRIPTION)
    repo.create_actual_session(session)
    repo.create_prescription_mapping(matching.prescription_mapping)
    duplicate = replace(value, component_results=(planned_result, extra_result, extra_result))
    with pytest.raises(ValueError):
        repo.create_execution_evaluation(duplicate)
    with sqlite3.connect(repo.database_path) as connection:
        assert connection.execute("SELECT count(*) FROM maintain_plan_execution_evaluations").fetchone() == (0,)
    repo.create_execution_evaluation(value)
    ghost = replace(extra_result, observed_component_ref=ObservedComponentRef(
        "foreign-session", "ghost"))
    tampered = replace(value, component_results=(planned_result, ghost))
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("UPDATE maintain_plan_execution_evaluations SET payload_json=?",
                           (serialize_contract(tampered),))
    with pytest.raises(ValueError):
        repo.get_execution_evaluation(value.evaluation_id)


def test_mapping_hierarchy_rejects_cross_component_blocks_repetitions_and_transitions(tmp_path):
    planned_components = tuple(replace(component, structure=replace(
        component.structure, blocks=(replace(component.structure.blocks[0],
            block_id=f"{component.component_id}-block", planned_repetitions=1),)))
        for component in BRICK_PRESCRIPTION.components)
    snapshot = replace(BRICK_PRESCRIPTION, components=planned_components)
    observed_components = (
        ObservedComponent("run", 0, Discipline.RUN, blocks=(ObservedBlock(
            "run-block", 0, repetitions=(ObservedRepetition("run-rep", 0, "run-block"),)),)),
        ObservedComponent("bike", 1, Discipline.BIKE, blocks=(ObservedBlock(
            "bike-block", 0, repetitions=(ObservedRepetition("bike-rep", 0, "bike-block"),)),)),
    )
    session = ActualSession("hierarchy", NOW, Composition.BRICK, observed_components,
        transition_ids=("observed-transition",), transitions=(ObservedTransition(
            "observed-transition", "run", "bike"),))
    mapping = build_mapping(snapshot, session, mapping_id="hierarchy-map", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    assert validate_mapping_ownership(mapping, snapshot, session) == ()
    swapped_blocks = replace(mapping, block_mappings=(
        replace(mapping.block_mappings[0], observed_block_ref=mapping.block_mappings[1].observed_block_ref),
        mapping.block_mappings[1]))
    assert validate_mapping_ownership(swapped_blocks, snapshot, session)
    swapped_repetitions = replace(mapping, repetition_mappings=(
        replace(mapping.repetition_mappings[0],
                observed_repetition_ref=mapping.repetition_mappings[1].observed_repetition_ref),
        mapping.repetition_mappings[1]))
    assert validate_mapping_ownership(swapped_repetitions, snapshot, session)
    reversed_session = replace(session, transitions=(ObservedTransition(
        "observed-transition", "bike", "run"),))
    assert validate_mapping_ownership(mapping, snapshot, reversed_session)
    repo = MaintainPlanRepository(tmp_path / "mapping-hierarchy.db")
    repo.create_prescription_snapshot(snapshot)
    repo.create_actual_session(session)
    with pytest.raises(ValueError):
        repo.create_prescription_mapping(swapped_blocks)
    assert repo.get_prescription_mapping("hierarchy-map") is None
    repo.create_prescription_mapping(mapping)
    with sqlite3.connect(repo.database_path) as connection:
        connection.execute("UPDATE maintain_plan_prescription_mappings SET payload_json=?",
                           (serialize_contract(swapped_blocks),))
    with pytest.raises(ValueError):
        repo.get_prescription_mapping("hierarchy-map")


def test_zero_candidate_confirmation_offers_and_resolves_all_normative_answers():
    session = _session("manual", start=NOW + timedelta(days=1))
    result = _match(RUN_PRESCRIPTION, (session,))
    request = request_confirmation(result, confirmation_id="zero", asked_at=NOW, provenance={})
    offered = {item["answer_type"] for item in request.interpretations}
    assert offered == {"NOT_PERFORMED", "NOT_SYNCHRONIZED", "DONT_KNOW", "MANUAL_ASSOCIATION"}
    for answer_type in (ConfirmationAnswerType.NOT_PERFORMED,
                        ConfirmationAnswerType.NOT_SYNCHRONIZED,
                        ConfirmationAnswerType.DONT_KNOW):
        answer, unresolved = answer_confirmation(
            request, result, RUN_PRESCRIPTION, (session,), confirmation_id=f"a-{answer_type.value}",
            matching_result_id=f"r-{answer_type.value}", mapping_id="unused",
            answer_type=answer_type, selected_session_ref=None, actor="athlete",
            answered_at=NOW, provenance={})
        assert unresolved.prescription_mapping is None
        assert answer.status is (ConfirmationStatus.UNKNOWN_ANSWER
                                 if answer_type is ConfirmationAnswerType.DONT_KNOW
                                 else ConfirmationStatus.ANSWERED)
    _, resolved = answer_confirmation(
        request, result, RUN_PRESCRIPTION, (session,), confirmation_id="manual-answer",
        matching_result_id="manual-result", mapping_id="manual-map",
        answer_type=ConfirmationAnswerType.MANUAL_ASSOCIATION, selected_session_ref="manual",
        actor="athlete", answered_at=NOW, provenance={})
    assert resolved.status is MatchingStatus.MATCHED
    with pytest.raises(ValueError):
        answer_confirmation(request, result, RUN_PRESCRIPTION, (session,),
            confirmation_id="bad", matching_result_id="bad", mapping_id="bad-map",
            answer_type=ConfirmationAnswerType.SELECT_CANDIDATE, selected_session_ref="manual",
            actor="athlete", answered_at=NOW, provenance={})


@pytest.mark.parametrize("changes", [
    {"answer_type": ConfirmationAnswerType.DONT_KNOW},
    {"actor": "athlete"}, {"answered_at": NOW},
    {"status": ConfirmationStatus.ANSWERED},
])
def test_confirmation_status_matrix_rejects_malformed_required(changes):
    result = _match(RUN_PRESCRIPTION, (_session("one"), _session("two")))
    request = request_confirmation(result, confirmation_id="q", asked_at=NOW, provenance={})
    assert validate_confirmation(replace(request, **changes))


@pytest.mark.parametrize("changes", [
    {"answer_type": None}, {"actor": None}, {"answered_at": None},
    {"selected_session_ref": None},
    {"status": ConfirmationStatus.UNKNOWN_ANSWER},
    {"asked_at": NOW.replace(tzinfo=None)}, {"answered_at": NOW.replace(tzinfo=None)},
    {"interpretations": ({"answer_type": "DONT_KNOW"},)},
    {"declared_session_refs": ("cross-session",)},
])
def test_confirmation_status_matrix_rejects_malformed_answered(changes):
    sessions = (_session("one"), _session("two"))
    result = _match(RUN_PRESCRIPTION, sessions)
    request = request_confirmation(result, confirmation_id="q", asked_at=NOW, provenance={})
    answered, _ = answer_confirmation(
        request, result, RUN_PRESCRIPTION, sessions, confirmation_id="a",
        matching_result_id="resolved", mapping_id="map",
        answer_type=ConfirmationAnswerType.SELECT_CANDIDATE, selected_session_ref="one",
        actor="athlete", answered_at=NOW, provenance={})
    assert validate_confirmation(replace(answered, **changes))


@pytest.mark.parametrize("answer_type,selected", [
    (ConfirmationAnswerType.NOT_PERFORMED, "one"),
    (ConfirmationAnswerType.NOT_SYNCHRONIZED, "one"),
    (ConfirmationAnswerType.DONT_KNOW, "one"),
])
def test_non_selecting_confirmation_answers_forbid_selected_session(answer_type, selected):
    result = _match(RUN_PRESCRIPTION, (_session("one"), _session("two")))
    request = request_confirmation(result, confirmation_id="q", asked_at=NOW, provenance={})
    with pytest.raises(ValueError):
        answer_confirmation(request, result, RUN_PRESCRIPTION,
            (_session("one"), _session("two")), confirmation_id="a",
            matching_result_id="r", mapping_id="m", answer_type=answer_type,
            selected_session_ref=selected, actor="athlete", answered_at=NOW, provenance={})
