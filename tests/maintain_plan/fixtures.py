"""Entirely synthetic MAINTAIN_PLAN contract fixtures."""

from dataclasses import replace
from datetime import datetime, timezone

from backend.maintain_plan.models import *

NOW = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
CAPABILITY = PolicyRef("maintain-plan-evaluator-capability", "1.0.0-draft")
AGGREGATION = PolicyRef("maintain-plan-component-aggregation", "1.0.0-draft")
DOSE_POLICY = PolicyRef("maintain-plan-dose-matrix", "1.0.0-draft")
NULL_POLICY = PolicyRef(None, None)
IDENTITY_POLICY = PolicyRef("maintain-plan-sport-taxonomy", "1.0.0-draft")
QUANTITY_POLICY = PolicyRef("maintain-plan-quantity", "1.0.0-draft")
CONTINUOUS_INTENSITY_POLICY = PolicyRef("maintain-plan-continuous-intensity", "1.0.0-draft")
INTERVAL_INTENSITY_POLICY = PolicyRef("maintain-plan-interval-intensity", "1.0.0-draft")
STRUCTURE_POLICY = PolicyRef("maintain-plan-structure", "1.0.0-draft")


def prescription(*components: PlannedComponent, composition=Composition.SINGLE, objective=None,
                 transitions=()):
    return PrescriptionSnapshot(
        "snapshot-1", "workout-1", "decision-1", NOW,
        ScheduledWindow(NOW, NOW, "UTC", False), composition, tuple(components), tuple(transitions),
        objective or Objective(ObjectiveEvaluability.CONTEXT_ONLY, None, context_text="synthetic", policy=NULL_POLICY),
        PolicyRef("maintain-plan-matching", "1.0.0-draft"),
        PolicyRef("maintain-plan-brick-consecutivity", "1.0.0-draft")
        if composition is Composition.BRICK else NULL_POLICY,
        Provenance("synthetic-fixture", NOW), PrescriptionAudit(None),
    )


def planned(component_id, index, discipline, requiredness=Requiredness.REQUIRED,
            support=SupportStatus.SUPPORTED, *, environment=Environment.OUTDOOR,
            mode=Mode.ROAD, quantity_target=None, intensity_target=None,
            session_type=SessionType.CONTINUOUS, blocks=None, substitutions=()):
    quantity_target = PrescribedTarget(60) if quantity_target is None else quantity_target
    intensity_target = PrescribedTarget("Z2") if intensity_target is None else intensity_target
    intensity_policy = (INTERVAL_INTENSITY_POLICY if session_type is SessionType.INTERVALS
                        else CONTINUOUS_INTENSITY_POLICY)
    if blocks is None:
        blocks = (PlannedBlock(
            f"{component_id}-main", 0, BlockType.MAIN_SET, Requiredness.REQUIRED,
            quantity_target, intensity_target, IntensityMethod.RPE, "RPE",
            intensity_target, EvaluationWindow.WHOLE_BLOCK, intensity_policy, None,
            RecoveryContract(Applicability.NOT_APPLICABLE, None), (), STRUCTURE_POLICY),)
    return PlannedComponent(
        component_id, index, discipline, environment, mode, requiredness, support,
        CAPABILITY, Applicability.REQUIRED, tuple(substitutions), IDENTITY_POLICY,
        QuantityContract(Applicability.REQUIRED, QuantityMetric.ACTIVE_DURATION,
                         quantity_target, "minutes", (), QUANTITY_POLICY, NULL_POLICY),
        IntensityContract(Applicability.REQUIRED, IntensityMethod.RPE,
                          intensity_target, "RPE", (), intensity_policy),
        StructureContract(Applicability.REQUIRED, session_type, STRUCTURE_POLICY,
                          tuple(blocks)),
        DoseContract(Applicability.REQUIRED, DOSE_POLICY,
                     f"quantity-{component_id}", f"intensity-{component_id}"),
    )


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


def execution(results, coverage=CoverageStatus.FULLY_SUPPORTED, snapshot=None):
    snapshot = snapshot or prescription(*(planned(r.planned_component_ref.component_id, index, Discipline.RUN,
                                                   r.requiredness, r.support_status)
                                          for index, r in enumerate(results)
                                          if r.planned_component_ref is not None),
                                        composition=Composition.SINGLE if len(results) == 1 else Composition.BRICK)
    full = coverage is CoverageStatus.FULLY_SUPPORTED
    aggregates = [DimensionAggregate(f"aggregate-{name}", AdherenceStatus.MET,
                                     tuple(r.component_result_id for r in results if r.requiredness is Requiredness.REQUIRED), AGGREGATION)
                  for name in ("identity", "quantity", "intensity", "structure")]
    return ExecutionEvaluation(
        "evaluation-1", "mapping-1", "snapshot-1", "session-1", tuple(results), None,
        EvaluationCoverage(coverage,
                           tuple(PlannedComponentRef(snapshot.prescription_snapshot_id, c.component_id) for c in snapshot.components if c.requiredness is Requiredness.REQUIRED and c.support_status is SupportStatus.SUPPORTED),
                           tuple(PlannedComponentRef(snapshot.prescription_snapshot_id, c.component_id) for c in snapshot.components if c.requiredness is Requiredness.REQUIRED and c.support_status is SupportStatus.UNSUPPORTED),
                           tuple(PlannedComponentRef(snapshot.prescription_snapshot_id, c.component_id) for c in snapshot.components if c.requiredness is Requiredness.OPTIONAL and c.support_status is SupportStatus.UNSUPPORTED), CAPABILITY),
        *(aggregates if full else (None, None, None, None)),
        DoseEvaluation("dose-aggregate", DoseStatus.EVALUATED, Direction.IN_LINE, SeverityBand.MAIN,
                       "aggregate-quantity", "aggregate-intensity", DOSE_POLICY) if full else None,
        OverallStatus.IN_LINE if full else None,
        PolicyRef("maintain-plan-execution-aggregation", "1.0.0-draft"),
    )


RUN_PRESCRIPTION = prescription(planned("run", 0, Discipline.RUN))
RUN_SESSION = ActualSession("session-1", NOW, Composition.SINGLE, (observed("run", 0, Discipline.RUN, {"seconds": 3600}),))
RUN_MAPPING = mapping((("run", "run", Requiredness.REQUIRED, SupportStatus.SUPPORTED),))
RUN_EXECUTION = execution((component_result("run"),), snapshot=RUN_PRESCRIPTION)

BRICK_PRESCRIPTION = prescription(
    planned("run", 0, Discipline.RUN, quantity_target=PrescribedTarget(30),
            intensity_target=PrescribedTarget("RUN_Z2")),
    planned("bike", 1, Discipline.BIKE, mode=Mode.ROAD,
            quantity_target=PrescribedTarget(75), intensity_target=PrescribedTarget(180)),
    composition=Composition.BRICK,
    transitions=(PlannedTransition(
        "run-to-bike", "run", "bike",
        PolicyRef("maintain-plan-brick-consecutivity", "1.0.0-draft"), 15),))
BRICK_SESSION = ActualSession("session-1", NOW, Composition.BRICK, (observed("run", 0, Discipline.RUN), observed("bike", 1, Discipline.BIKE)))
BRICK_MAPPING = mapping((("run", "run", Requiredness.REQUIRED, SupportStatus.SUPPORTED),
                         ("bike", "bike", Requiredness.REQUIRED, SupportStatus.SUPPORTED)))
BRICK_EXECUTION = execution((component_result("run"), component_result("bike")), snapshot=BRICK_PRESCRIPTION)

STRENGTH_REQUIRED = component_result("strength", support=SupportStatus.UNSUPPORTED)
STRENGTH_PRESCRIPTION = prescription(planned("strength", 0, Discipline.STRENGTH, support=SupportStatus.UNSUPPORTED))
STRENGTH_MAPPING = mapping((("strength", "strength", Requiredness.REQUIRED, SupportStatus.UNSUPPORTED),))
STRENGTH_EXECUTION = execution((STRENGTH_REQUIRED,), CoverageStatus.UNSUPPORTED, STRENGTH_PRESCRIPTION)
OPTIONAL_PLANNED_ONLY = component_result("swim", requiredness=Requiredness.OPTIONAL, match=MatchStatus.PLANNED_ONLY)
OBSERVED_ONLY_EXTRA = component_result("extra", match=MatchStatus.OBSERVED_ONLY)
PARTIAL_POLICY = PolicyRef("policy", None)
INVALID_STRUCTURED = Objective(ObjectiveEvaluability.STRUCTURED, None, policy=NULL_POLICY)
INVALID_EVALUATED_DOSE = DoseEvaluation("bad-dose", DoseStatus.EVALUATED, None, None, "q", "i", NULL_POLICY)
INVALID_NON_FULL_AGGREGATES = replace(RUN_EXECUTION, evaluation_coverage=replace(RUN_EXECUTION.evaluation_coverage, status=CoverageStatus.UNSUPPORTED))

INTERVAL_BLOCK = PlannedBlock(
    "run-work", 0, BlockType.WORK, Requiredness.REQUIRED,
    PrescribedTarget(400), PrescribedTarget(None, 4, 5), IntensityMethod.RPE,
    "RPE", PrescribedTarget(None, 4, 5), EvaluationWindow.AVERAGE,
    INTERVAL_INTENSITY_POLICY, 6,
    RecoveryContract(Applicability.REQUIRED, PrescribedTarget(90)),
    ("after warmup",), STRUCTURE_POLICY,
)
INTERVAL_PRESCRIPTION = prescription(planned(
    "run", 0, Discipline.RUN, session_type=SessionType.INTERVALS,
    quantity_target=PrescribedTarget(2400), intensity_target=PrescribedTarget(None, 4, 5),
    blocks=(INTERVAL_BLOCK,)))
