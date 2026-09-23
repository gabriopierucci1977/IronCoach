from dataclasses import replace
from datetime import timedelta, timezone
import ast
from pathlib import Path

import pytest

from backend.maintain_plan.models import (
    ActualSession, AllowedSubstitution, Composition, Discipline, Environment, Mode,
    ObservedTransition, PlannedTransition, PolicyRef, SupportStatus,
)
from backend.maintain_plan.runtime_matching_compatibility import (
    CompatibilityInputError, CompatibilityReason, CompatibilityState,
    StructuralCompatibility, evaluate_structural_compatibility,
)
from tests.maintain_plan.fixtures import (
    BRICK_PRESCRIPTION, NOW, NULL_POLICY, RUN_PRESCRIPTION, RUN_SESSION,
    observed, planned, prescription,
)


SUBSTITUTION_POLICY = PolicyRef("substitution", "1")
BRICK_POLICY = PolicyRef("maintain-plan-brick-consecutivity", "1.0.0-draft")


def result(snapshot, session):
    return evaluate_structural_compatibility(snapshot, session)


def multisport():
    snapshot = prescription(
        planned("swim", 0, Discipline.SWIM, environment=Environment.OUTDOOR,
                mode=Mode.OPEN_WATER),
        planned("bike", 1, Discipline.BIKE, environment=Environment.OUTDOOR,
                mode=Mode.ROAD),
        composition=Composition.MULTISPORT,
    )
    session = ActualSession(
        "multi", NOW, Composition.MULTISPORT,
        (observed("s", 0, Discipline.SWIM), observed("b", 1, Discipline.BIKE)),
        subject_ref="athlete-1",
    )
    return snapshot, session


def brick(*, gap=15, limit=15, transitions=True):
    first = replace(observed("run-observed", 0, Discipline.RUN),
                    start=NOW, end=NOW + timedelta(minutes=30))
    second = replace(observed("bike-observed", 1, Discipline.BIKE),
                     start=first.end + timedelta(minutes=gap),
                     end=first.end + timedelta(minutes=gap + 60))
    observed_transition = ObservedTransition(
        "transition", first.component_id, second.component_id,
        first.end, second.start, gap,
    )
    session = ActualSession(
        "brick", NOW, Composition.BRICK, (first, second),
        transition_ids=("transition",) if transitions else (),
        transitions=(observed_transition,) if transitions else (),
        subject_ref="athlete-1",
    )
    planned_transition = PlannedTransition(
        "planned-transition", "run", "bike", BRICK_POLICY, limit)
    snapshot = replace(BRICK_PRESCRIPTION, transitions=(planned_transition,))
    return snapshot, session


def assert_reason(snapshot, session, reason):
    evaluated = result(snapshot, session)
    assert evaluated.state is CompatibilityState.INCOMPATIBLE
    assert reason in evaluated.reasons


def test_single_exact_discipline_is_compatible_and_result_is_immutable():
    evaluated = result(RUN_PRESCRIPTION, RUN_SESSION)
    assert evaluated == StructuralCompatibility(CompatibilityState.COMPATIBLE)
    with pytest.raises(AttributeError):
        evaluated.state = CompatibilityState.INCOMPATIBLE


def test_single_substitution_is_component_scoped():
    substitution = AllowedSubstitution(
        Discipline.BIKE, Environment.OUTDOOR, Mode.ROAD, SUBSTITUTION_POLICY)
    component = replace(RUN_PRESCRIPTION.components[0],
                        allowed_substitutions=(substitution,))
    snapshot = replace(RUN_PRESCRIPTION, components=(component,))
    compatible = replace(RUN_SESSION, components=(replace(
        RUN_SESSION.components[0], discipline=Discipline.BIKE,
        environment=Environment.OUTDOOR, mode=Mode.ROAD),))
    assert result(snapshot, compatible).state is CompatibilityState.COMPATIBLE

    unrelated = planned("bike", 1, Discipline.BIKE, substitutions=(
        AllowedSubstitution(Discipline.SWIM, None, None, SUBSTITUTION_POLICY),))
    multi_snapshot = prescription(component, unrelated, composition=Composition.MULTISPORT)
    multi_session = ActualSession(
        "multi", NOW, Composition.MULTISPORT,
        (replace(compatible.components[0], component_index=0),
         observed("second", 1, Discipline.SWIM)), subject_ref="athlete-1")
    assert result(multi_snapshot, multi_session).state is CompatibilityState.COMPATIBLE
    inherited = replace(multi_session, components=(
        replace(multi_session.components[0], discipline=Discipline.SWIM),
        multi_session.components[1]))
    assert_reason(multi_snapshot, inherited, CompatibilityReason.COMPONENT_DISCIPLINE)


@pytest.mark.parametrize("components", [(),
    (RUN_SESSION.components[0], replace(RUN_SESSION.components[0],
                                        component_id="extra", component_index=1))])
def test_single_rejects_missing_or_extra_evidence(components):
    session = replace(RUN_SESSION, components=components)
    with pytest.raises(CompatibilityInputError):
        result(RUN_PRESCRIPTION, session)


def test_substitutions_are_not_transitive():
    substitution = AllowedSubstitution(Discipline.BIKE, None, None, SUBSTITUTION_POLICY)
    snapshot = replace(RUN_PRESCRIPTION, components=(replace(
        RUN_PRESCRIPTION.components[0], allowed_substitutions=(substitution,)),))
    session = replace(RUN_SESSION, components=(replace(
        RUN_SESSION.components[0], discipline=Discipline.SWIM),))
    assert_reason(snapshot, session, CompatibilityReason.COMPONENT_DISCIPLINE)


@pytest.mark.parametrize(
    ("environment", "mode", "state", "reason"),
    [
        (Environment.OUTDOOR, Mode.ROAD, CompatibilityState.COMPATIBLE, None),
        (None, None, CompatibilityState.COMPATIBLE, None),
        (Environment.INDOOR, Mode.ROAD, CompatibilityState.INCOMPATIBLE,
         CompatibilityReason.COMPONENT_ENVIRONMENT),
        (Environment.OUTDOOR, Mode.TRAIL, CompatibilityState.INCOMPATIBLE,
         CompatibilityReason.COMPONENT_MODE),
    ],
)
def test_exact_discipline_environment_and_mode_rules(environment, mode, state, reason):
    session = replace(RUN_SESSION, components=(replace(
        RUN_SESSION.components[0], environment=environment, mode=mode),))
    evaluated = result(RUN_PRESCRIPTION, session)
    assert evaluated.state is state
    if reason:
        assert reason in evaluated.reasons


def test_substitution_environment_and_mode_rules_are_local_and_alternative():
    substitutions = (
        AllowedSubstitution(Discipline.BIKE, Environment.INDOOR, Mode.INDOOR_TRAINER,
                            SUBSTITUTION_POLICY),
        AllowedSubstitution(Discipline.BIKE, Environment.OUTDOOR, Mode.ROAD,
                            SUBSTITUTION_POLICY),
    )
    snapshot = replace(RUN_PRESCRIPTION, components=(replace(
        RUN_PRESCRIPTION.components[0], allowed_substitutions=substitutions),))
    session = replace(RUN_SESSION, components=(replace(
        RUN_SESSION.components[0], discipline=Discipline.BIKE,
        environment=Environment.OUTDOOR, mode=Mode.ROAD),))
    assert result(snapshot, session).state is CompatibilityState.COMPATIBLE
    missing = replace(session, components=(replace(session.components[0],
                                                    environment=None, mode=None),))
    assert result(snapshot, missing).state is CompatibilityState.COMPATIBLE
    contradiction = replace(session, components=(replace(
        session.components[0], environment=Environment.OUTDOOR, mode=Mode.TRAIL),))
    assert result(snapshot, contradiction).state is CompatibilityState.INCOMPATIBLE


def test_valid_brick_is_unsupported_because_interposition_is_unprovable():
    snapshot, session = brick()
    assert result(snapshot, session) == StructuralCompatibility(
        CompatibilityState.UNSUPPORTED,
        (CompatibilityReason.BRICK_INTERPOSITION_UNPROVABLE,),
    )


def test_no_valid_brick_fixture_can_return_compatible():
    for gap, limit in ((0, 0), (15, 15), (16, 20)):
        evaluated = result(*brick(gap=gap, limit=limit))
        assert evaluated.state is CompatibilityState.UNSUPPORTED
        assert evaluated.state is not CompatibilityState.COMPATIBLE


def test_brick_wrong_order_is_incompatible_not_unsupported():
    snapshot, session = brick()
    session = replace(session, components=(
        replace(session.components[0], discipline=Discipline.BIKE),
        replace(session.components[1], discipline=Discipline.RUN)))
    assert_reason(snapshot, session, CompatibilityReason.COMPONENT_DISCIPLINE)


@pytest.mark.parametrize("kind", ("missing", "dangling", "outside", "duration"))
def test_brick_missing_or_invalid_transition_is_incompatible(kind):
    snapshot, session = brick()
    if kind == "missing":
        session = replace(session, transition_ids=(), transitions=())
    else:
        transition = session.transitions[0]
        if kind == "dangling":
            transition = replace(transition, from_component_ref=session.components[1].component_id,
                                 to_component_ref=session.components[0].component_id)
        elif kind == "outside":
            transition = replace(transition, start=session.components[0].start,
                                 end=session.components[0].end)
        else:
            transition = replace(transition, duration_minutes=14)
        session = replace(session, transitions=(transition,))
    assert_reason(snapshot, session, CompatibilityReason.BRICK_TRANSITION_INVALID)


@pytest.mark.parametrize("target", ("component", "transition"))
def test_brick_insufficient_timing_evidence_is_incompatible(target):
    snapshot, session = brick()
    if target == "component":
        session = replace(session, components=(replace(session.components[0], end=None),
                                               session.components[1]))
    else:
        session = replace(session, transitions=(replace(session.transitions[0], start=None),))
    assert_reason(snapshot, session, CompatibilityReason.BRICK_TIMING_INSUFFICIENT)


def test_brick_overlap_is_incompatible():
    snapshot, session = brick()
    session = replace(session, components=(session.components[0], replace(
        session.components[1], start=session.components[0].end - timedelta(seconds=1))))
    transition = replace(session.transitions[0], end=session.transitions[0].start,
                         duration_minutes=0)
    session = replace(session, transitions=(transition,))
    assert_reason(snapshot, session, CompatibilityReason.BRICK_COMPONENT_OVERLAP)


@pytest.mark.parametrize(("gap", "state"), [(15, CompatibilityState.UNSUPPORTED),
                                               (15.01, CompatibilityState.INCOMPATIBLE)])
def test_brick_explicit_maximum_gap_closed_boundary(gap, state):
    evaluated = result(*brick(gap=gap, limit=15))
    assert evaluated.state is state
    if state is CompatibilityState.INCOMPATIBLE:
        assert CompatibilityReason.BRICK_MAXIMUM_GAP_EXCEEDED in evaluated.reasons


@pytest.mark.parametrize("limit", (1e100, 1_440_000_000_000.0))
def test_finite_but_unrepresentable_maximum_gap_is_specific_input_error(limit):
    snapshot, session = brick(limit=limit)
    with pytest.raises(CompatibilityInputError,
                       match="snapshot transition maximum gap is invalid"):
        result(snapshot, session)


@pytest.mark.parametrize("orientation", ("reversed", "nonadjacent"))
def test_every_written_transition_limit_is_validated(orientation):
    snapshot, session = brick()
    transition = snapshot.transitions[0]
    if orientation == "reversed":
        transition = replace(
            transition, from_component_id="bike", to_component_id="run",
            applicable_limit_minutes=float("nan"))
        snapshot = replace(snapshot, transitions=(transition,))
    else:
        third = replace(snapshot.components[1], component_id="third", component_index=2)
        transition = replace(
            transition, from_component_id="run", to_component_id="third",
            applicable_limit_minutes=-1)
        snapshot = replace(snapshot, components=snapshot.components + (third,),
                           transitions=(transition,))
    with pytest.raises(CompatibilityInputError,
                       match="snapshot transition maximum gap is invalid"):
        result(snapshot, session)


@pytest.mark.parametrize(("gap", "state"), [(15, CompatibilityState.UNSUPPORTED),
                                               (15.01, CompatibilityState.INCOMPATIBLE)])
def test_brick_default_fifteen_minute_gap_closed_boundary(gap, state):
    snapshot, session = brick(gap=gap)
    snapshot = replace(snapshot, transitions=())
    evaluated = result(snapshot, session)
    assert evaluated.state is state
    if state is CompatibilityState.INCOMPATIBLE:
        assert CompatibilityReason.BRICK_MAXIMUM_GAP_EXCEEDED in evaluated.reasons


def test_brick_nonconsecutive_components_are_incompatible():
    snapshot, session = brick()
    session = replace(session, components=(session.components[0], replace(
        session.components[1], component_index=2)))
    assert_reason(snapshot, session, CompatibilityReason.COMPONENT_ORDER)


def test_unrelated_interposed_activity_is_not_inferred_or_inspected():
    snapshot, session = brick()
    session = replace(session, source_activities=())
    assert result(snapshot, session).reasons == (
        CompatibilityReason.BRICK_INTERPOSITION_UNPROVABLE,)


def test_multisport_is_compatible_without_brick_transitions_timing_or_gap_policy():
    snapshot, session = multisport()
    assert snapshot.brick_policy == NULL_POLICY
    assert session.transitions == ()
    assert all(component.start is None for component in session.components)
    assert result(snapshot, session).state is CompatibilityState.COMPATIBLE


@pytest.mark.parametrize("mutation", ("wrong_order", "missing", "extra"))
def test_multisport_wrong_order_and_cardinality(mutation):
    snapshot, session = multisport()
    if mutation == "wrong_order":
        session = replace(session, components=(
            replace(session.components[0], discipline=Discipline.BIKE),
            replace(session.components[1], discipline=Discipline.SWIM)))
        assert result(snapshot, session).state is CompatibilityState.INCOMPATIBLE
    elif mutation == "missing":
        with pytest.raises(CompatibilityInputError):
            result(snapshot, replace(session, components=session.components[:1]))
    else:
        extra = observed("extra", 2, Discipline.RUN)
        assert_reason(snapshot, replace(session, components=session.components + (extra,)),
                      CompatibilityReason.COMPONENT_CARDINALITY)


@pytest.mark.parametrize("composition", (Composition.SINGLE, Composition.BRICK,
                                           Composition.MULTISPORT))
@pytest.mark.parametrize(("offset", "inside"), [(-0.001, False), (0, True),
                                                  (60, True), (60.001, False)])
def test_closed_scheduled_window_for_every_composition(composition, offset, inside):
    if composition is Composition.SINGLE:
        snapshot, session = RUN_PRESCRIPTION, RUN_SESSION
    elif composition is Composition.BRICK:
        snapshot, session = brick()
    else:
        snapshot, session = multisport()
    snapshot = replace(snapshot, scheduled_window=replace(
        snapshot.scheduled_window, start=NOW, end=NOW + timedelta(minutes=60)))
    session = replace(session, start=NOW + timedelta(minutes=offset))
    evaluated = result(snapshot, session)
    assert (CompatibilityReason.SCHEDULED_WINDOW not in evaluated.reasons) is inside


@pytest.mark.parametrize("composition", (Composition.SINGLE, Composition.BRICK,
                                           Composition.MULTISPORT))
def test_point_windows_and_timezone_equivalent_instants(composition):
    if composition is Composition.SINGLE:
        snapshot, session = RUN_PRESCRIPTION, RUN_SESSION
    elif composition is Composition.BRICK:
        snapshot, session = brick()
    else:
        snapshot, session = multisport()
    session = replace(session, start=NOW.astimezone(timezone(timedelta(hours=2))))
    assert CompatibilityReason.SCHEDULED_WINDOW not in result(snapshot, session).reasons
    assert_reason(snapshot, replace(session, start=session.start + timedelta(microseconds=1)),
                  CompatibilityReason.SCHEDULED_WINDOW)


@pytest.mark.parametrize(("side", "value"), [("snapshot", "brick"),
                                                ("session", None),
                                                ("session", "future")])
def test_unknown_or_undecodable_composition_is_corruption(side, value):
    snapshot, session = RUN_PRESCRIPTION, RUN_SESSION
    if side == "snapshot":
        snapshot = replace(snapshot, composition=value)
    else:
        session = replace(session, composition=value)
    with pytest.raises(CompatibilityInputError, match="unknown or undecodable"):
        result(snapshot, session)


@pytest.mark.parametrize("side", ("snapshot", "session"))
def test_completely_malformed_component_is_specific_input_corruption(side):
    snapshot, session = RUN_PRESCRIPTION, RUN_SESSION
    if side == "snapshot":
        snapshot = replace(snapshot, components=(None,))
    else:
        session = replace(session, components=(None,))
    with pytest.raises(CompatibilityInputError, match=f"{side} component is malformed"):
        result(snapshot, session)


def test_valid_deliberately_unsupported_capability_is_unsupported():
    snapshot = replace(RUN_PRESCRIPTION, components=(replace(
        RUN_PRESCRIPTION.components[0], discipline=Discipline.STRENGTH,
        support_status=SupportStatus.UNSUPPORTED),))
    session = replace(RUN_SESSION, components=(replace(
        RUN_SESSION.components[0], discipline=Discipline.STRENGTH),))
    assert result(snapshot, session) == StructuralCompatibility(
        CompatibilityState.UNSUPPORTED, (CompatibilityReason.CAPABILITY_UNSUPPORTED,))


def test_result_is_independent_of_nonsemantic_tuple_ordering():
    snapshot, session = multisport()
    reversed_snapshot = replace(snapshot, components=tuple(reversed(snapshot.components)))
    reversed_session = replace(session, components=tuple(reversed(session.components)))
    assert result(snapshot, session) == result(reversed_snapshot, reversed_session)


def test_direct_id_evidence_is_not_accepted_or_inspected():
    with pytest.raises(TypeError, match="direct_id_evidence"):
        evaluate_structural_compatibility(
            RUN_PRESCRIPTION, RUN_SESSION, direct_id_evidence=(object(),))


def test_module_has_no_repository_provider_history_or_persistence_dependency():
    path = Path("backend/maintain_plan/runtime_matching_compatibility.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = ("repository", "provider", "history", "persistence", "sqlite")
    assert not any(word in name.lower() for name in imported for word in forbidden)
