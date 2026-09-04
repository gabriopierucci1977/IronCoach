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
    assert validate_execution_evaluation(RUN_EXECUTION, RUN_MAPPING) == ()
    assert validate_prescription(BRICK_PRESCRIPTION) == ()
    assert validate_actual_session(BRICK_SESSION) == ()
    assert validate_mapping(BRICK_MAPPING) == ()
    assert validate_execution_evaluation(BRICK_EXECUTION, BRICK_MAPPING) == ()
    assert validate_prescription(STRENGTH_PRESCRIPTION) == ()
    assert validate_execution_evaluation(STRENGTH_EXECUTION, RUN_MAPPING) == ()


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
    assert expected_coverage(results) is expected


def test_aggregates_exist_only_for_full_coverage():
    assert "non-FULLY_SUPPORTED" in " ".join(validate_execution_evaluation(INVALID_NON_FULL_AGGREGATES, RUN_MAPPING))
    unsupported = execution((STRENGTH_REQUIRED,), CoverageStatus.UNSUPPORTED)
    assert validate_execution_evaluation(unsupported, RUN_MAPPING) == ()
    assert unsupported.identity_aggregate is unsupported.dose_aggregate is unsupported.overall is None


def test_dose_status_controls_results_and_policy():
    assert validate_dose(INVALID_EVALUATED_DOSE)
    insufficient = DoseEvaluation("dose-missing", DoseStatus.INSUFFICIENT_DATA, None, None, None, None, NULL_POLICY)
    assert validate_dose(insufficient) == ()
    assert validate_dose(replace(insufficient, direction=Direction.IN_LINE))


def test_execution_identifies_canonical_mapping():
    assert validate_execution_evaluation(replace(RUN_EXECUTION, prescription_mapping_ref="unknown"), RUN_MAPPING)


def test_missing_quantity_is_preserved_and_never_coerced_to_zero():
    missing = observed("run", 0, Discipline.RUN)
    assert missing.quantity_observation is None
