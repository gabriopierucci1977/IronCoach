"""Deterministic execution evaluation over canonical MAINTAIN_PLAN objects only."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

from .models import *
from .validators import (validate_actual_session, validate_execution_evaluation,
                         validate_mapping_ownership, validate_prescription)

CAPABILITY = PolicyRef("maintain-plan-evaluator-capability", "1.0.0-draft")
AGGREGATION = PolicyRef("maintain-plan-component-aggregation", "1.0.0-draft")
EXECUTION = PolicyRef("maintain-plan-execution-aggregation", "1.0.0-draft")
COMPOSITION = PolicyRef("maintain-plan-session-composition", "1.0.0-draft")
DOSE = PolicyRef("maintain-plan-dose-matrix", "1.0.0-draft")
NULL_POLICY = PolicyRef(None, None)


def evaluate_source_conflict_impact(session: ActualSession, mapping: PrescriptionMapping,
                                    conflict: Mapping, *, impact_evaluation_id: str,
                                    evaluation_version: str, evaluated_at: datetime,
                                    provenance: Mapping | None = None) -> SourceConflictImpactEvaluation:
    """Classify only dimensions explicitly identified by a canonical field path."""
    errors = validate_actual_session(session)
    if errors or mapping.actual_session_ref != session.session_id:
        raise ValueError("source conflict impact requires the exact canonical session and mapping")
    conflict_id, path = conflict.get("conflict_id"), conflict.get("field_path")
    if not isinstance(conflict_id, str) or not isinstance(path, str):
        raise ValueError("source conflict requires conflict_id and field_path")
    if sum(item.get("conflict_id") == conflict_id for item in session.source_conflicts) != 1:
        raise ValueError("source conflict reference is ghost or duplicated")
    dimensions = []
    tokens = set(path.replace("[", ".").replace("]", "").split("."))
    if tokens & {"discipline", "environment", "mode", "composition"}:
        dimensions.append(AffectedDimension.IDENTITY)
    if tokens & {"quantity_observation", "quantity_primary_metric", "quantity_unit", "distance", "active_duration"}:
        dimensions.append(AffectedDimension.QUANTITY)
    if tokens & {"intensity_observations", "intensity_methods", "time_in_target", "valid_coverage"}:
        dimensions.append(AffectedDimension.INTENSITY)
    if tokens & {"blocks", "repetitions", "transitions", "block_index", "repetition_index", "duration_minutes"}:
        dimensions.append(AffectedDimension.STRUCTURE)
    status = ConflictImpactStatus.EVALUATED
    return SourceConflictImpactEvaluation(
        impact_evaluation_id, evaluation_version, SourceConflictRef(session.session_id, conflict_id),
        mapping.mapping_id, status, tuple(dimensions),
        PolicyRef("maintain-plan-source-conflict-impact", "1.0.0-draft"),
        provenance or {}, evaluated_at, (), ())


def _precedence(statuses):
    for status in (AdherenceStatus.INSUFFICIENT_DATA, AdherenceStatus.NOT_MET,
                   AdherenceStatus.PARTIALLY_MET, AdherenceStatus.MET):
        if status in statuses:
            return status
    raise ValueError("cannot aggregate an empty result set")


def _quantity(component: PlannedComponent, observed: ObservedComponent, result_id: str):
    target = component.quantity.target
    data = observed.quantity_observation
    metric = observed.quantity_primary_metric
    if target is None or target.value is None or not isinstance(target.value, (int, float)):
        return DimensionResult(result_id, AdherenceStatus.INSUFFICIENT_DATA,
                               component.quantity.policy, missing_fields=("quantity.target",))
    if not data or metric != component.quantity.primary_metric.value or observed.quantity_unit != component.quantity.unit:
        return DimensionResult(result_id, AdherenceStatus.INSUFFICIENT_DATA,
                               component.quantity.policy,
                               missing_fields=("quantity_observation",))
    value = data.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return DimensionResult(result_id, AdherenceStatus.INSUFFICIENT_DATA,
                               component.quantity.policy,
                               missing_fields=("quantity_observation.value",))
    ratio = value / target.value if target.value else None
    if ratio is None:
        return DimensionResult(result_id, AdherenceStatus.INSUFFICIENT_DATA,
                               component.quantity.policy, missing_fields=("quantity.target.value",))
    # The v1 table has the same duration bands for supported continuous sports.
    if .90 <= ratio <= 1.05:
        status, direction, band = AdherenceStatus.MET, Direction.IN_LINE, SeverityBand.MAIN
    elif .80 <= ratio <= 1.15:
        status, direction, band = AdherenceStatus.PARTIALLY_MET, (Direction.LOWER if ratio < .9 else Direction.HIGHER), SeverityBand.SECONDARY
    else:
        status, direction, band = AdherenceStatus.NOT_MET, (Direction.LOWER if ratio < .8 else Direction.HIGHER), SeverityBand.OUT_OF_BAND
    return DimensionResult(result_id, status, component.quantity.policy, direction, band,
                           {"planned": target.value, "observed": value, "unit": component.quantity.unit})


def _intensity(component: PlannedComponent, observed: ObservedComponent, result_id: str):
    data = observed.intensity_observations
    method = component.intensity.primary_method.value
    if not data or method not in observed.intensity_methods:
        return DimensionResult(result_id, AdherenceStatus.INSUFFICIENT_DATA,
                               component.intensity.policy, missing_fields=("intensity_observations",))
    valid = data.get("valid_coverage")
    target = data.get("time_in_target")
    if not isinstance(valid, (int, float)) or not isinstance(target, (int, float)) or valid < .8:
        return DimensionResult(result_id, AdherenceStatus.INSUFFICIENT_DATA,
                               component.intensity.policy, missing_fields=("intensity.valid_coverage",))
    if target >= .8:
        return DimensionResult(result_id, AdherenceStatus.MET, component.intensity.policy,
                               Direction.IN_LINE, SeverityBand.MAIN, data)
    status = AdherenceStatus.PARTIALLY_MET if target >= .6 else AdherenceStatus.NOT_MET
    band = SeverityBand.SECONDARY if target >= .6 else SeverityBand.OUT_OF_BAND
    above, below = data.get("time_above"), data.get("time_below")
    direction = (Direction.UNDETERMINED if not isinstance(above, (int, float)) or not isinstance(below, (int, float))
                 else Direction.HIGHER if above > below else Direction.LOWER if below > above else Direction.MIXED)
    return DimensionResult(result_id, status, component.intensity.policy, direction, band, data)


def _dose(result_id, quantity, intensity, now):
    if (quantity.status is AdherenceStatus.INSUFFICIENT_DATA or
            intensity.status is AdherenceStatus.INSUFFICIENT_DATA or
            quantity.band is None or intensity.band is None):
        return DoseEvaluation(result_id, DoseStatus.INSUFFICIENT_DATA, None, None,
                              quantity.result_id, intensity.result_id, NULL_POLICY, computed_at=now,
                              missing_fields=("quantity_or_intensity",))
    directions = {quantity.direction, intensity.direction}
    if Direction.UNDETERMINED in directions: direction = Direction.UNDETERMINED
    elif Direction.MIXED in directions or {Direction.LOWER, Direction.HIGHER} <= directions: direction = Direction.MIXED
    elif Direction.HIGHER in directions: direction = Direction.HIGHER
    elif Direction.LOWER in directions: direction = Direction.LOWER
    else: direction = Direction.IN_LINE
    severity = max((quantity.band, intensity.band), key=lambda x: list(SeverityBand).index(x))
    return DoseEvaluation(result_id, DoseStatus.EVALUATED, direction, severity,
                          quantity.result_id, intensity.result_id, DOSE, computed_at=now)


def evaluate(snapshot: PrescriptionSnapshot, session: ActualSession, mapping: PrescriptionMapping,
             *, evaluation_id: str, evaluated_at: datetime,
             conflict_projections: tuple[SourceConflictProjection, ...] = (),
             conflict_impacts: tuple[SourceConflictImpactEvaluation, ...] = (),
             provenance: Mapping | None = None) -> ExecutionEvaluation:
    """Evaluate every canonical component mapping exactly once or publish nothing."""
    errors = (*validate_prescription(snapshot), *validate_actual_session(session),
              *validate_mapping_ownership(mapping, snapshot, session))
    if errors:
        raise ValueError("; ".join(errors))
    conflict_ids = [item.get("conflict_id") for item in session.source_conflicts]
    if len(conflict_ids) != len(set(conflict_ids)):
        raise ValueError("canonical source conflicts must be unique")
    if len({p.projection_id for p in conflict_projections}) != len(conflict_projections):
        raise ValueError("source-conflict projections must not be duplicated")
    if len({i.conflict_impact_evaluation_id for i in conflict_impacts}) != len(conflict_impacts):
        raise ValueError("conflict impacts must not be duplicated")
    for projection in conflict_projections:
        if (projection.actual_session_ref.session_id != session.session_id or
                conflict_ids.count(projection.source_conflict_id) != 1):
            raise ValueError("source-conflict projection is ghost or foreign-session")
    for impact in conflict_impacts:
        if (impact.prescription_mapping_ref != mapping.mapping_id or
                impact.source_conflict_ref.session_id != session.session_id or
                conflict_ids.count(impact.source_conflict_ref.conflict_id) != 1):
            raise ValueError("conflict impact is ghost, foreign-session, or cross-mapping")
    planned = {x.component_id: x for x in snapshot.components}
    observed = {x.component_id: x for x in session.components}
    conflicts = {item.get("conflict_id"): item for item in session.source_conflicts}
    blocking_conflicts = {p.source_conflict_id for p in conflict_projections
                          if p.status is not SourceConflictProjectionStatus.RESOLVED}
    results = []
    planned_order = {component.component_id: component.component_index for component in snapshot.components}
    observed_order = {component.component_id: component.component_index for component in session.components}
    component_mappings = sorted(mapping.component_mappings, key=lambda item: (
        planned_order.get(item.planned_component_ref.component_id, 10**9)
        if item.planned_component_ref else 10**9,
        observed_order.get(item.observed_component_ref.component_id, 10**9)
        if item.observed_component_ref else 10**9))
    for index, item in enumerate(component_mappings):
        rid = f"{evaluation_id}:component:{index}"
        p = None if item.planned_component_ref is None else planned[item.planned_component_ref.component_id]
        o = None if item.observed_component_ref is None else observed[item.observed_component_ref.component_id]
        component_ids = {x.component_id for x in (p, o) if x is not None}
        unresolved = set()
        for impact in conflict_impacts:
            if (impact.status is ConflictImpactStatus.UNRESOLVED or
                    impact.source_conflict_ref.conflict_id in blocking_conflicts):
                pass
            else:
                continue
            path = str(conflicts.get(impact.source_conflict_ref.conflict_id, {}).get("field_path", ""))
            mentioned = {component_id for component_id in planned | observed if component_id in path.split(".")}
            if not mentioned or mentioned & component_ids:
                unresolved.update(impact.affected_dimensions)
        applicable = not (item.match_status is MatchStatus.PLANNED_ONLY and item.requiredness is Requiredness.OPTIONAL)
        dimensions = [None] * 4; dose = None
        if item.support_status is SupportStatus.SUPPORTED and applicable and item.match_status is not MatchStatus.OBSERVED_ONLY:
            if o is None:
                dimensions = [DimensionResult(f"{rid}:identity", AdherenceStatus.NOT_MET, p.identity_policy),
                              DimensionResult(f"{rid}:quantity", AdherenceStatus.INSUFFICIENT_DATA, p.quantity.policy, missing_fields=("observed_component",)),
                              DimensionResult(f"{rid}:intensity", AdherenceStatus.INSUFFICIENT_DATA, p.intensity.policy, missing_fields=("observed_component",)),
                              DimensionResult(f"{rid}:structure", AdherenceStatus.NOT_MET, p.structure.policy)]
            else:
                identity = AdherenceStatus.MET if (o.discipline is p.discipline and o.environment is p.environment and o.mode is p.mode) else (AdherenceStatus.INSUFFICIENT_DATA if None in (o.discipline, o.environment, o.mode) else AdherenceStatus.NOT_MET)
                block_maps = [b for b in mapping.block_mappings if (b.planned_block_ref and b.planned_block_ref.component_id == p.component_id) or (b.observed_block_ref and b.observed_block_ref.component_id == o.component_id)]
                structure = (AdherenceStatus.NOT_MET if any(b.match_status is MatchStatus.PLANNED_ONLY for b in block_maps) else
                             AdherenceStatus.MET if block_maps or not p.structure.blocks else AdherenceStatus.INSUFFICIENT_DATA)
                dimensions = [DimensionResult(f"{rid}:identity", identity, p.identity_policy),
                              _quantity(p, o, f"{rid}:quantity"), _intensity(p, o, f"{rid}:intensity"),
                              DimensionResult(f"{rid}:structure", structure, p.structure.policy)]
            for pos, affected in enumerate((AffectedDimension.IDENTITY, AffectedDimension.QUANTITY, AffectedDimension.INTENSITY, AffectedDimension.STRUCTURE)):
                if affected in unresolved:
                    old = dimensions[pos]
                    dimensions[pos] = DimensionResult(old.result_id, AdherenceStatus.INSUFFICIENT_DATA, old.policy,
                                                      missing_fields=("unresolved_source_conflict",))
            dose = _dose(f"{rid}:dose", dimensions[1], dimensions[2], evaluated_at)
        results.append(ComponentEvaluation(rid, item.match_status, item.requiredness,
            EvaluationApplicability.APPLICABLE if applicable else EvaluationApplicability.NOT_APPLICABLE,
            item.support_status, item.capability_policy, item.planned_component_ref,
            item.observed_component_ref, *dimensions, dose, provenance or {}, item.missing_fields, item.warnings))
    required = [p for p in snapshot.components if p.requiredness is Requiredness.REQUIRED]
    supported = [p for p in required if p.support_status is SupportStatus.SUPPORTED]
    coverage_status = CoverageStatus.NO_REQUIRED_COMPONENTS if not required else CoverageStatus.FULLY_SUPPORTED if len(supported)==len(required) else CoverageStatus.UNSUPPORTED if not supported else CoverageStatus.PARTIALLY_UNSUPPORTED
    coverage = EvaluationCoverage(coverage_status,
        tuple(PlannedComponentRef(snapshot.prescription_snapshot_id,p.component_id) for p in supported),
        tuple(PlannedComponentRef(snapshot.prescription_snapshot_id,p.component_id) for p in required if p not in supported),
        tuple(PlannedComponentRef(snapshot.prescription_snapshot_id,p.component_id) for p in snapshot.components if p.requiredness is Requiredness.OPTIONAL and p.support_status is SupportStatus.UNSUPPORTED), CAPABILITY)
    extras = tuple(r.observed_component_ref for r in results if r.match_status is MatchStatus.OBSERVED_ONLY)
    missing = tuple(r.planned_component_ref for r in results if r.match_status is MatchStatus.PLANNED_ONLY and r.requiredness is Requiredness.REQUIRED)
    comp_status = AdherenceStatus.NOT_MET if extras else AdherenceStatus.NOT_MET if missing else AdherenceStatus.MET
    composition = SessionCompositionResult(f"{evaluation_id}:composition", comp_status,
        tuple(PlannedComponentRef(snapshot.prescription_snapshot_id,p.component_id) for p in snapshot.components),
        tuple(ObservedComponentRef(session.session_id,o.component_id) for o in session.components), extras, missing, COMPOSITION)
    aggregates = [None] * 4; aggregate_dose = overall = None
    if coverage_status is CoverageStatus.FULLY_SUPPORTED:
        applicable_results = [r for r in results if r.requiredness is Requiredness.REQUIRED]
        for pos, name in enumerate(("identity","quantity","intensity","structure")):
            statuses = [getattr(r,name).status for r in applicable_results]
            if name == "identity": statuses.append(composition.status)
            direction = None
            if name == "intensity" and AdherenceStatus.INSUFFICIENT_DATA not in statuses:
                dirs={r.intensity.direction for r in applicable_results}
                direction = Direction.UNDETERMINED if Direction.UNDETERMINED in dirs else Direction.MIXED if Direction.MIXED in dirs or {Direction.LOWER,Direction.HIGHER}<=dirs else Direction.HIGHER if Direction.HIGHER in dirs else Direction.LOWER if Direction.LOWER in dirs else Direction.IN_LINE
            aggregates[pos] = DimensionAggregate(f"{evaluation_id}:aggregate:{name}", _precedence(statuses), tuple(r.component_result_id for r in applicable_results), AGGREGATION, direction)
        component_doses = [r.dose for r in applicable_results]
        if any(d.status is DoseStatus.INSUFFICIENT_DATA for d in component_doses):
            aggregate_dose = DoseEvaluation(f"{evaluation_id}:dose:aggregate", DoseStatus.INSUFFICIENT_DATA,
                None, None, aggregates[1].result_id, aggregates[2].result_id, NULL_POLICY, computed_at=evaluated_at,
                missing_fields=("component_dose",))
        else:
            directions={d.direction for d in component_doses}
            direction = Direction.UNDETERMINED if Direction.UNDETERMINED in directions else Direction.MIXED if Direction.MIXED in directions or {Direction.LOWER,Direction.HIGHER}<=directions else Direction.HIGHER if Direction.HIGHER in directions else Direction.LOWER if Direction.LOWER in directions else Direction.IN_LINE
            severity=max((d.severity_band for d in component_doses), key=lambda x:list(SeverityBand).index(x))
            aggregate_dose = DoseEvaluation(f"{evaluation_id}:dose:aggregate", DoseStatus.EVALUATED,
                direction, severity, aggregates[1].result_id, aggregates[2].result_id, DOSE,
                computed_at=evaluated_at)
        statuses=[a.status for a in aggregates]
        overall = OverallStatus.INSUFFICIENT_DATA if AdherenceStatus.INSUFFICIENT_DATA in statuses else OverallStatus.DIFFERENT if AdherenceStatus.NOT_MET in statuses else OverallStatus.PARTIALLY_IN_LINE if AdherenceStatus.PARTIALLY_MET in statuses else OverallStatus.IN_LINE
    projection_refs=tuple(SourceConflictProjectionRef(p.projection_id,p.projection_version,p.projection_hash,p.projection_hash_algorithm,p.projection_serialization_policy_id,p.projection_serialization_policy_version) for p in conflict_projections)
    impact_refs=tuple(ConflictImpactEvaluationRef(i.conflict_impact_evaluation_id,i.evaluation_version) for i in conflict_impacts)
    value=ExecutionEvaluation(evaluation_id,mapping.mapping_id,snapshot.prescription_snapshot_id,session.session_id,tuple(results),composition,coverage,*aggregates,aggregate_dose,overall,EXECUTION,projection_refs,impact_refs,provenance or {})
    validation=validate_execution_evaluation(value,mapping,snapshot,session)
    if validation: raise ValueError("; ".join(validation))
    return value


class ExecutionEvaluationService:
    """Namespace matching the other isolated MAINTAIN_PLAN domain services."""

    evaluate = staticmethod(evaluate)
    evaluate_source_conflict_impact = staticmethod(evaluate_source_conflict_impact)
