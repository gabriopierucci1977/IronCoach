"""Entirely synthetic MAINTAIN_PLAN contract fixtures."""

from dataclasses import replace
from datetime import datetime, timezone

from backend.maintain_plan.models import *

NOW = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
CAPABILITY = PolicyRef("maintain-plan-evaluator-capability", "1.0.0-draft")
AGGREGATION = PolicyRef("maintain-plan-component-aggregation", "1.0.0-draft")
DOSE_POLICY = PolicyRef("maintain-plan-dose-matrix", "1.0.0-draft")
NULL_POLICY = PolicyRef(None, None)


def prescription(*components: PlannedComponent, composition=Composition.SINGLE, objective=None):
    return PrescriptionSnapshot(
        "snapshot-1", "workout-1", "decision-1", NOW, composition, tuple(components),
        objective or Objective(ObjectiveEvaluability.CONTEXT_ONLY, None, context_text="synthetic", policy=NULL_POLICY),
        PolicyRef("maintain-plan-matching", "1.0.0-draft"),
    )


def planned(component_id, index, discipline, requiredness=Requiredness.REQUIRED, support=SupportStatus.SUPPORTED):
    return PlannedComponent(component_id, index, discipline, requiredness, support, CAPABILITY)


def observed(component_id, index, discipline, quantity=None):
    return ObservedComponent(component_id, index, discipline, quantity_observation=quantity)


def mapping(component_pairs):
    return PrescriptionMapping(
        "mapping-1", "snapshot-1", "session-1", ResolutionMethod.AUTOMATIC,
        tuple(ComponentMapping(PlannedComponentRef("snapshot-1", p), ObservedComponentRef("session-1", o), r, s, CAPABILITY)
              for p, o, r, s in component_pairs),
    )


def dimension(result_id):
    return DimensionResult(result_id, AdherenceStatus.MET, AGGREGATION)


def component_result(component_id, observed_id=None, *, requiredness=Requiredness.REQUIRED,
                     support=SupportStatus.SUPPORTED, match=MatchStatus.MATCHED):
    applicable = not (requiredness is Requiredness.OPTIONAL and match is MatchStatus.PLANNED_ONLY)
    has_results = support is SupportStatus.SUPPORTED and applicable and match is not MatchStatus.OBSERVED_ONLY
    return ComponentEvaluation(
        f"result-{component_id}", match,
        None if match is MatchStatus.OBSERVED_ONLY else requiredness,
        EvaluationApplicability.APPLICABLE if applicable else EvaluationApplicability.NOT_APPLICABLE,
        support, CAPABILITY,
        None if match is MatchStatus.OBSERVED_ONLY else PlannedComponentRef("snapshot-1", component_id),
        None if match is MatchStatus.PLANNED_ONLY else ObservedComponentRef("session-1", observed_id or component_id),
        *(dimension(f"{kind}-{component_id}") if has_results else None for kind in ("identity", "quantity", "intensity", "structure")),
        DoseEvaluation(f"dose-{component_id}", DoseStatus.EVALUATED, Direction.IN_LINE, SeverityBand.MAIN,
                       f"quantity-{component_id}", f"intensity-{component_id}", DOSE_POLICY) if has_results else None,
    )


def execution(results, coverage=CoverageStatus.FULLY_SUPPORTED):
    full = coverage is CoverageStatus.FULLY_SUPPORTED
    aggregates = [DimensionAggregate(f"aggregate-{name}", AdherenceStatus.MET,
                                     tuple(r.component_result_id for r in results if r.requiredness is Requiredness.REQUIRED), AGGREGATION)
                  for name in ("identity", "quantity", "intensity", "structure")]
    return ExecutionEvaluation(
        "evaluation-1", "mapping-1", "snapshot-1", "session-1", tuple(results), None,
        EvaluationCoverage(coverage,
                           tuple(r.planned_component_ref for r in results if r.requiredness is Requiredness.REQUIRED and r.support_status is SupportStatus.SUPPORTED),
                           tuple(r.planned_component_ref for r in results if r.requiredness is Requiredness.REQUIRED and r.support_status is SupportStatus.UNSUPPORTED),
                           tuple(r.planned_component_ref for r in results if r.requiredness is Requiredness.OPTIONAL and r.support_status is SupportStatus.UNSUPPORTED), CAPABILITY),
        *(aggregates if full else (None, None, None, None)),
        DoseEvaluation("dose-aggregate", DoseStatus.EVALUATED, Direction.IN_LINE, SeverityBand.MAIN,
                       "aggregate-quantity", "aggregate-intensity", DOSE_POLICY) if full else None,
        OverallStatus.IN_LINE if full else None,
        PolicyRef("maintain-plan-execution-aggregation", "1.0.0-draft"),
    )


RUN_PRESCRIPTION = prescription(planned("run", 0, Discipline.RUN))
RUN_SESSION = ActualSession("session-1", NOW, Composition.SINGLE, (observed("run", 0, Discipline.RUN, {"seconds": 3600}),))
RUN_MAPPING = mapping((("run", "run", Requiredness.REQUIRED, SupportStatus.SUPPORTED),))
RUN_EXECUTION = execution((component_result("run"),))

BRICK_PRESCRIPTION = prescription(planned("run", 0, Discipline.RUN), planned("bike", 1, Discipline.BIKE), composition=Composition.BRICK)
BRICK_SESSION = ActualSession("session-1", NOW, Composition.BRICK, (observed("run", 0, Discipline.RUN), observed("bike", 1, Discipline.BIKE)))
BRICK_MAPPING = mapping((("run", "run", Requiredness.REQUIRED, SupportStatus.SUPPORTED),
                         ("bike", "bike", Requiredness.REQUIRED, SupportStatus.SUPPORTED)))
BRICK_EXECUTION = execution((component_result("run"), component_result("bike")))

STRENGTH_REQUIRED = component_result("strength", support=SupportStatus.UNSUPPORTED)
STRENGTH_PRESCRIPTION = prescription(planned("strength", 0, Discipline.STRENGTH, support=SupportStatus.UNSUPPORTED))
STRENGTH_EXECUTION = execution((STRENGTH_REQUIRED,), CoverageStatus.UNSUPPORTED)
OPTIONAL_PLANNED_ONLY = component_result("swim", requiredness=Requiredness.OPTIONAL, match=MatchStatus.PLANNED_ONLY)
OBSERVED_ONLY_EXTRA = component_result("extra", match=MatchStatus.OBSERVED_ONLY)
PARTIAL_POLICY = PolicyRef("policy", None)
INVALID_STRUCTURED = Objective(ObjectiveEvaluability.STRUCTURED, None, policy=NULL_POLICY)
INVALID_EVALUATED_DOSE = DoseEvaluation("bad-dose", DoseStatus.EVALUATED, None, None, "q", "i", NULL_POLICY)
INVALID_NON_FULL_AGGREGATES = replace(RUN_EXECUTION, evaluation_coverage=replace(RUN_EXECUTION.evaluation_coverage, status=CoverageStatus.UNSUPPORTED))
