from dataclasses import FrozenInstanceError, replace

import pytest

from backend.maintain_plan.models import *
from backend.maintain_plan.validators import *
from tests.maintain_plan.fixtures import *


def test_contracts_are_immutable():
    with pytest.raises(FrozenInstanceError):
        RUN_PRESCRIPTION.workout_id = "changed"
    assert dataclass_is_frozen(RUN_SESSION)


def test_valid_single_run_and_brick_fixtures():
    assert validate_prescription(RUN_PRESCRIPTION) == ()
    assert validate_actual_session(RUN_SESSION) == ()
    assert validate_mapping(RUN_MAPPING) == ()
    assert validate_execution_evaluation(RUN_EXECUTION, RUN_MAPPING, RUN_PRESCRIPTION) == ()
    assert validate_prescription(BRICK_PRESCRIPTION) == ()
    assert validate_actual_session(BRICK_SESSION) == ()
    assert validate_mapping(BRICK_MAPPING) == ()
    assert validate_execution_evaluation(BRICK_EXECUTION, BRICK_MAPPING, BRICK_PRESCRIPTION) == ()
    assert validate_prescription(STRENGTH_PRESCRIPTION) == ()
    assert validate_mapping(STRENGTH_MAPPING) == ()
    assert validate_execution_evaluation(STRENGTH_EXECUTION, STRENGTH_MAPPING, STRENGTH_PRESCRIPTION) == ()


def test_policy_pair_and_structured_objective_invariants():
    assert validate_policy_ref(PARTIAL_POLICY)
    assert validate_prescription(replace(RUN_PRESCRIPTION, objective=INVALID_STRUCTURED))
    valid = Objective(ObjectiveEvaluability.STRUCTURED, "steady-finish", ({"metric": "pace"},), policy=PolicyRef("objective-policy", "1"))
    assert validate_prescription(replace(RUN_PRESCRIPTION, objective=valid)) == ()
    # Free text remains context only: validators never derive code, criteria, or results from it.
    assert RUN_PRESCRIPTION.objective.code is None


def test_references_are_fully_qualified_and_ids_unique_in_scope():
    bad_mapping = replace(RUN_MAPPING, component_mappings=(replace(RUN_MAPPING.component_mappings[0], planned_component_ref=PlannedComponentRef("other", "run")),))
    assert "qualified" in " ".join(validate_mapping(bad_mapping))
    duplicate = replace(RUN_SESSION, components=(RUN_SESSION.components[0], RUN_SESSION.components[0]))
    assert "unique" in " ".join(validate_actual_session(duplicate))


def test_observed_only_optional_omission_and_unsupported_rules():
    assert validate_component_evaluation(OBSERVED_ONLY_EXTRA) == ()
    assert OBSERVED_ONLY_EXTRA.requiredness is None
    assert validate_component_evaluation(OPTIONAL_PLANNED_ONLY) == ()
    assert OPTIONAL_PLANNED_ONLY.evaluation_applicability is EvaluationApplicability.NOT_APPLICABLE
    assert all(getattr(OPTIONAL_PLANNED_ONLY, name) is None for name in ("identity", "quantity", "intensity", "structure", "dose"))
    assert validate_component_evaluation(STRENGTH_REQUIRED) == ()
    assert all(getattr(STRENGTH_REQUIRED, name) is None for name in ("identity", "quantity", "intensity", "structure", "dose"))


@pytest.mark.parametrize(("results", "expected"), [
    ((component_result("run"),), CoverageStatus.FULLY_SUPPORTED),
    ((component_result("run"), STRENGTH_REQUIRED), CoverageStatus.PARTIALLY_UNSUPPORTED),
    ((STRENGTH_REQUIRED,), CoverageStatus.UNSUPPORTED),
    ((OPTIONAL_PLANNED_ONLY, OBSERVED_ONLY_EXTRA), CoverageStatus.NO_REQUIRED_COMPONENTS),
])
def test_distinct_evaluation_coverage(results, expected):
    components = tuple(planned(r.planned_component_ref.component_id, index, Discipline.RUN,
                               r.requiredness, r.support_status)
                       for index, r in enumerate(results) if r.planned_component_ref)
    snapshot = prescription(*components, composition=Composition.SINGLE if len(components) == 1 else Composition.BRICK)
    assert expected_coverage(snapshot) is expected


def test_aggregates_exist_only_for_full_coverage():
    assert "non-FULLY_SUPPORTED" in " ".join(validate_execution_evaluation(INVALID_NON_FULL_AGGREGATES, RUN_MAPPING, RUN_PRESCRIPTION))
    unsupported = execution((STRENGTH_REQUIRED,), CoverageStatus.UNSUPPORTED, STRENGTH_PRESCRIPTION)
    assert validate_execution_evaluation(unsupported, STRENGTH_MAPPING, STRENGTH_PRESCRIPTION) == ()
    assert unsupported.identity_aggregate is unsupported.dose_aggregate is unsupported.overall is None


def test_dose_status_controls_results_and_policy():
    assert validate_dose(INVALID_EVALUATED_DOSE)
    insufficient = DoseEvaluation("dose-missing", DoseStatus.INSUFFICIENT_DATA, None, None, None, None, NULL_POLICY)
    assert validate_dose(insufficient) == ()
    assert validate_dose(replace(insufficient, direction=Direction.IN_LINE))


def test_execution_identifies_canonical_mapping():
    assert validate_execution_evaluation(replace(RUN_EXECUTION, prescription_mapping_ref="unknown"), RUN_MAPPING, RUN_PRESCRIPTION)


def test_missing_quantity_is_preserved_and_never_coerced_to_zero():
    missing = observed("run", 0, Discipline.RUN)
    assert missing.quantity_observation is None


def test_payloads_are_defensively_copied_and_deeply_immutable():
    original = {"samples": [{"seconds": 60}], "labels": {"steady"}}
    component = observed("run", 0, Discipline.RUN, original)
    original["samples"][0]["seconds"] = 99
    original["labels"].add("changed")
    assert component.quantity_observation["samples"][0]["seconds"] == 60
    assert component.quantity_observation["labels"] == frozenset({"steady"})
    with pytest.raises(TypeError):
        component.quantity_observation["new"] = True
    with pytest.raises(TypeError):
        component.quantity_observation["samples"][0]["seconds"] = 10

    criteria = [{"ranges": [1, {"codes": {"A", "B"}}]}]
    objective = Objective(ObjectiveEvaluability.STRUCTURED, "code", criteria,
                          policy=PolicyRef("objective", "1"))
    criteria[0]["ranges"].append(2)
    assert len(objective.success_criteria[0]["ranges"]) == 2
    with pytest.raises(AttributeError):
        objective.success_criteria[0]["ranges"].append(3)


@pytest.mark.parametrize(("composition", "components"), [
    (Composition.SINGLE, ()),
    (Composition.SINGLE, (planned("run", 0, Discipline.RUN), planned("bike", 1, Discipline.BIKE))),
    (Composition.BRICK, (planned("run", 0, Discipline.RUN),)),
    (Composition.MULTISPORT, (planned("run", 0, Discipline.RUN),)),
])
def test_prescription_composition_cardinality(composition, components):
    assert "component" in " ".join(validate_prescription(prescription(*components, composition=composition)))


def test_mapping_rejects_ambiguous_duplicates_and_allows_multiple_null_observed_refs():
    first = RUN_MAPPING.component_mappings[0]
    duplicate_planned = replace(first, observed_component_ref=ObservedComponentRef("session-1", "other"))
    assert "planned component" in " ".join(validate_mapping(replace(RUN_MAPPING, component_mappings=(first, duplicate_planned))))

    bike = replace(first, planned_component_ref=PlannedComponentRef("snapshot-1", "bike"))
    assert "observed component" in " ".join(validate_mapping(replace(RUN_MAPPING, component_mappings=(first, bike))))
    assert validate_mapping(BRICK_MAPPING) == ()

    null_run = replace(first, observed_component_ref=None)
    null_bike = replace(bike, observed_component_ref=None)
    assert validate_mapping(replace(RUN_MAPPING, component_mappings=(null_run, null_bike))) == ()


@pytest.mark.parametrize("refs", [
    (),
    ("result-run", "result-run", "result-bike"),
    ("result-run", "unknown"),
])
def test_aggregate_component_references_must_be_complete_unique_and_known(refs):
    invalid = replace(BRICK_EXECUTION,
                      quantity_aggregate=replace(BRICK_EXECUTION.quantity_aggregate,
                                                 component_result_refs=refs))
    assert "quantity aggregate" in " ".join(
        validate_execution_evaluation(invalid, BRICK_MAPPING, BRICK_PRESCRIPTION))


def test_aggregate_rejects_result_not_applicable_to_required_dimension():
    optional = component_result("swim", requiredness=Requiredness.OPTIONAL,
                                match=MatchStatus.PLANNED_ONLY)
    snapshot = prescription(planned("run", 0, Discipline.RUN),
                            planned("swim", 1, Discipline.SWIM, Requiredness.OPTIONAL),
                            composition=Composition.BRICK)
    mapped = mapping((("run", "run", Requiredness.REQUIRED, SupportStatus.SUPPORTED),
                      ("swim", "swim", Requiredness.OPTIONAL, SupportStatus.SUPPORTED)))
    evaluation = execution((component_result("run"), optional), snapshot=snapshot)
    invalid = replace(evaluation, identity_aggregate=replace(
        evaluation.identity_aggregate, component_result_refs=("result-run", "result-swim")))
    assert "identity aggregate" in " ".join(
        validate_execution_evaluation(invalid, mapped, snapshot))


def test_evaluated_dose_requires_resolvable_local_inputs():
    missing = replace(RUN_EXECUTION.component_results[0].dose, quantity_result_ref=None)
    invalid_component = replace(RUN_EXECUTION.component_results[0], dose=missing)
    invalid = replace(RUN_EXECUTION, component_results=(invalid_component,))
    errors = " ".join(validate_execution_evaluation(invalid, RUN_MAPPING, RUN_PRESCRIPTION))
    assert "quantity" in errors and "own quantity" in errors

    dangling = replace(RUN_EXECUTION.component_results[0].dose, intensity_result_ref="unknown")
    invalid = replace(RUN_EXECUTION, component_results=(replace(RUN_EXECUTION.component_results[0], dose=dangling),))
    assert "own quantity and intensity" in " ".join(
        validate_execution_evaluation(invalid, RUN_MAPPING, RUN_PRESCRIPTION))

    cross_component = replace(BRICK_EXECUTION.component_results[0].dose,
                              intensity_result_ref="intensity-bike")
    invalid = replace(BRICK_EXECUTION, component_results=(
        replace(BRICK_EXECUTION.component_results[0], dose=cross_component),
        BRICK_EXECUTION.component_results[1]))
    assert "own quantity and intensity" in " ".join(
        validate_execution_evaluation(invalid, BRICK_MAPPING, BRICK_PRESCRIPTION))
    assert validate_execution_evaluation(RUN_EXECUTION, RUN_MAPPING, RUN_PRESCRIPTION) == ()


def test_aggregate_dose_references_this_evaluations_aggregates():
    dangling = replace(RUN_EXECUTION.dose_aggregate, quantity_result_ref="unknown")
    invalid = replace(RUN_EXECUTION, dose_aggregate=dangling)
    assert "aggregate dose" in " ".join(
        validate_execution_evaluation(invalid, RUN_MAPPING, RUN_PRESCRIPTION))


def test_coverage_uses_authoritative_prescription_and_requires_every_required_result():
    omitted = execution((component_result("run"),), snapshot=BRICK_PRESCRIPTION)
    errors = " ".join(validate_execution_evaluation(omitted, BRICK_MAPPING, BRICK_PRESCRIPTION))
    assert "each required planned component" in errors

    duplicate = replace(BRICK_EXECUTION, component_results=(
        BRICK_EXECUTION.component_results[0], BRICK_EXECUTION.component_results[0],
        BRICK_EXECUTION.component_results[1]))
    assert "exactly one component result" in " ".join(
        validate_execution_evaluation(duplicate, BRICK_MAPPING, BRICK_PRESCRIPTION))

    wrong_snapshot = replace(RUN_PRESCRIPTION, prescription_snapshot_id="other")
    assert "authoritative prescription" in " ".join(
        validate_execution_evaluation(RUN_EXECUTION, RUN_MAPPING, wrong_snapshot))
