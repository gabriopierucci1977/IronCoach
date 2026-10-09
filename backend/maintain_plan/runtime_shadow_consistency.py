"""Pure consistency boundary for one explicit runtime shadow chain."""

from dataclasses import dataclass

from .final_outcome_validators import validate_final_outcome_inputs
from .models import ActualSession, ExecutionEvaluation, PrescriptionMapping, PrescriptionSnapshot, ResolutionMethod
from .runtime_matching_decision import CandidateCardinality, CandidatePair, DecisionStatus, MatchingDecision, decide_runtime_matching
from .runtime_matching_scope import validate_runtime_matching_scope
from .stability_models import GeneralStabilityEvaluation


@dataclass(frozen=True)
class RuntimeShadowConsistency:
    subject_ref: str
    matching: MatchingDecision
    snapshot: PrescriptionSnapshot
    session: ActualSession
    mapping: PrescriptionMapping
    execution: ExecutionEvaluation
    stability: GeneralStabilityEvaluation


class RuntimeShadowConsistencyError(ValueError):
    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def validate_runtime_shadow_consistency(*, subject_ref, matching, snapshot, session, mapping, execution, stability):
    errors = []
    expected = ((matching, MatchingDecision, "matching"), (snapshot, PrescriptionSnapshot, "snapshot"), (session, ActualSession, "session"), (mapping, PrescriptionMapping, "mapping"), (execution, ExecutionEvaluation, "execution"), (stability, GeneralStabilityEvaluation, "stability"))
    for value, expected_type, label in expected:
        if type(value) is not expected_type:
            errors.append(f"{label} must be a {expected_type.__name__}")
    if errors:
        raise RuntimeShadowConsistencyError(errors)

    scope = validate_runtime_matching_scope(subject_ref, (snapshot,), (session,))
    authoritative = decide_runtime_matching(scope)
    if matching != authoritative:
        errors.append("matching does not equal the authoritative decision")

    selected = matching.selected_pair
    if (matching.status is not DecisionStatus.MATCHED or matching.cardinality is not CandidateCardinality.ONE or type(selected) is not CandidatePair):
        errors.append("consistency requires one globally matched CandidatePair")
    else:
        if mapping.prescription_snapshot_ref != selected.prescription_snapshot_id:
            errors.append("mapping snapshot ref does not equal selected pair")
        if mapping.actual_session_ref != selected.session_id:
            errors.append("mapping session ref does not equal selected pair")
        if execution.prescription_snapshot_ref != selected.prescription_snapshot_id:
            errors.append("execution snapshot ref does not equal selected pair")
        if execution.actual_session_ref != selected.session_id:
            errors.append("execution session ref does not equal selected pair")

    if mapping.resolution_method is not ResolutionMethod.AUTOMATIC:
        errors.append("shadow consistency requires an automatic mapping")
    if execution.prescription_mapping_ref != mapping.mapping_id:
        errors.append("execution mapping ref does not equal mapping.mapping_id")

    valid_planned = {(snapshot.prescription_snapshot_id, item.component_id) for item in snapshot.components}
    valid_observed = {(session.session_id, item.component_id) for item in session.components}
    for index, item in enumerate(mapping.component_mappings):
        planned = item.planned_component_ref
        observed = item.observed_component_ref
        if planned is not None and (planned.prescription_snapshot_id, planned.component_id) not in valid_planned:
            errors.append(f"component mapping {index} has unknown planned ref")
        if observed is not None and (observed.session_id, observed.component_id) not in valid_observed:
            errors.append(f"component mapping {index} has unknown observed ref")

    errors.extend(validate_final_outcome_inputs(execution, stability))
    if errors:
        raise RuntimeShadowConsistencyError(errors)
    return RuntimeShadowConsistency(subject_ref, matching, snapshot, session, mapping, execution, stability)
