"""Deterministic execution evaluation over canonical MAINTAIN_PLAN objects only."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Mapping

from .models import *
from .lifecycle_service import validate_source_conflict_projection
from .validators import (validate_actual_session, validate_execution_evaluation,
                         validate_mapping_ownership, validate_prescription,
                         validate_source_conflict_impact)

CAPABILITY = PolicyRef("maintain-plan-evaluator-capability", "1.0.0-draft")
AGGREGATION = PolicyRef("maintain-plan-component-aggregation", "1.0.0-draft")
EXECUTION = PolicyRef("maintain-plan-execution-aggregation", "1.0.0-draft")
COMPOSITION = PolicyRef("maintain-plan-session-composition", "1.0.0-draft")
DOSE = PolicyRef("maintain-plan-dose-matrix", "1.0.0-draft")
NULL_POLICY = PolicyRef(None, None)

_FIELD_PATHS = (
    (re.compile(r"^components\.(?P<component>[^.]+)\.(discipline|environment|mode)$"),
     (AffectedDimension.IDENTITY, AffectedDimension.DECISION)),
    (re.compile(r"^components\.(?P<component>[^.]+)\.(quantity_observation|quantity_primary_metric|quantity_unit)$"),
     (AffectedDimension.QUANTITY, AffectedDimension.DOSE, AffectedDimension.DECISION)),
    (re.compile(r"^components\.(?P<component>[^.]+)\.(intensity_observations|intensity_methods|temporal_coverage)$"),
     (AffectedDimension.INTENSITY, AffectedDimension.DOSE, AffectedDimension.DECISION)),
    (re.compile(r"^components\.(?P<component>[^.]+)\.blocks\.[^.]+\.(block_index|block_type|repetitions|quantity_observation|intensity_observation)$"),
     (AffectedDimension.STRUCTURE, AffectedDimension.DECISION)),
    (re.compile(r"^transitions\.[^.]+\.(from_component_ref|to_component_ref|start|end|duration_minutes)$"),
     (AffectedDimension.STRUCTURE, AffectedDimension.DECISION)),
    (re.compile(r"^composition$"), (AffectedDimension.IDENTITY, AffectedDimension.DECISION)),
)


def classify_source_conflict_field_path(path: str) -> tuple[AffectedDimension, ...]:
    if type(path) is not str:
        return ()
    for pattern, dimensions in _FIELD_PATHS:
        if pattern.fullmatch(path):
            return dimensions
    return ()


def evaluate_source_conflict_impact(session: ActualSession, mapping: PrescriptionMapping | None,
                                    conflict: Mapping, *, impact_evaluation_id: str,
                                    evaluation_version: str, evaluated_at: datetime,
                                    provenance: Mapping | None = None) -> SourceConflictImpactEvaluation:
    """Classify only dimensions explicitly identified by a canonical field path."""
    errors = validate_actual_session(session)
    if errors or (mapping is not None and mapping.actual_session_ref != session.session_id):
        raise ValueError("source conflict impact requires the exact canonical session")
    conflict_id, path = conflict.get("conflict_id"), conflict.get("field_path")
    if not isinstance(conflict_id, str) or not isinstance(path, str):
        raise ValueError("source conflict requires conflict_id and field_path")
    if sum(item.get("conflict_id") == conflict_id for item in session.source_conflicts) != 1:
        raise ValueError("source conflict reference is ghost or duplicated")
    dimensions = classify_source_conflict_field_path(path)
    status = ConflictImpactStatus.EVALUATED if mapping is not None else ConflictImpactStatus.UNRESOLVED
    return SourceConflictImpactEvaluation(
        impact_evaluation_id, evaluation_version, SourceConflictRef(session.session_id, conflict_id),
        None if mapping is None else mapping.mapping_id, status, dimensions,
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
    if component.structure.session_type is SessionType.INTERVALS:
        main_low, secondary_low, main_high, secondary_high = .95, .80, 1.05, 1.15
    elif (component.discipline is Discipline.SWIM and
          component.quantity.primary_metric is QuantityMetric.DISTANCE and
          component.mode is Mode.POOL):
        main_low, secondary_low, main_high, secondary_high = .95, .90, 1.05, 1.10
    elif component.quantity.primary_metric is QuantityMetric.ACTIVE_DURATION:
        main_low, secondary_low, main_high, secondary_high = .90, .80, 1.05, 1.15
    else:
        return DimensionResult(result_id, AdherenceStatus.INSUFFICIENT_DATA,
            component.quantity.policy,
            missing_fields=("quantity.quantity_band_policy_ref",))
    if main_low <= ratio <= main_high:
        status, direction, band = AdherenceStatus.MET, Direction.IN_LINE, SeverityBand.MAIN
    elif secondary_low <= ratio <= secondary_high:
        status, direction, band = AdherenceStatus.PARTIALLY_MET, (Direction.LOWER if ratio < main_low else Direction.HIGHER), SeverityBand.SECONDARY
    else:
        status, direction, band = AdherenceStatus.NOT_MET, (Direction.LOWER if ratio < secondary_low else Direction.HIGHER), SeverityBand.OUT_OF_BAND
    return DimensionResult(result_id, status, component.quantity.policy, direction, band,
                           {"planned": target.value, "observed": value, "unit": component.quantity.unit})


def _ratio(value):
    if type(value) is not dict and not hasattr(value, "get"):
        return None
    result = value.get("value")
    return result if type(result) in (int, float) and 0 <= result <= 1 else None


def _mapped_block(component, observed, planned_block, mapping, snapshot, session):
    planned_ref = PlannedBlockRef(snapshot.prescription_snapshot_id,
                                  component.component_id, planned_block.block_id)
    matches = [item for item in mapping.block_mappings
               if item.planned_block_ref == planned_ref]
    if len(matches) != 1 or matches[0].match_status is not MatchStatus.MATCHED or matches[0].observed_block_ref is None:
        return None
    observed_ref = matches[0].observed_block_ref
    if (observed_ref.session_id != session.session_id or
            observed_ref.component_id != observed.component_id):
        return None
    blocks = [item for item in observed.blocks if item.block_id == observed_ref.block_id]
    return blocks[0] if len(blocks) == 1 else None


def _mapped_repetition(component, observed, planned_block, repetition_index,
                       observed_block, mapping, snapshot, session):
    planned_ref = PlannedRepetitionRef(snapshot.prescription_snapshot_id,
        component.component_id, planned_block.block_id, repetition_index)
    matches = [item for item in mapping.repetition_mappings
               if item.planned_repetition_ref == planned_ref]
    if len(matches) != 1 or matches[0].match_status is not MatchStatus.MATCHED or matches[0].observed_repetition_ref is None:
        return None
    observed_ref = matches[0].observed_repetition_ref
    if (observed_ref.session_id != session.session_id or
            observed_ref.component_id != observed.component_id or
            observed_ref.block_id != observed_block.block_id):
        return None
    repetitions = [item for item in observed_block.repetitions
                   if item.repetition_id == observed_ref.repetition_id]
    return repetitions[0] if len(repetitions) == 1 else None


def _interval_intensity(component: PlannedComponent, observed: ObservedComponent,
                        mapping, snapshot, session, result_id: str):
    required = [b for b in component.structure.blocks if b.requiredness is Requiredness.REQUIRED]
    repetitions = []
    missing = []
    for block in required:
        if block.planned_repetitions is None:
            continue
        actual_block = _mapped_block(component, observed, block, mapping, snapshot, session)
        if actual_block is None or block.evaluation_window is None:
            missing.append(block.block_id); continue
        for repetition_index in range(block.planned_repetitions):
            repetition = _mapped_repetition(component, observed, block, repetition_index,
                actual_block, mapping, snapshot, session)
            if repetition is None:
                missing.append(f"{block.block_id}:{repetition_index}"); continue
            coverage = _ratio(repetition.valid_coverage)
            target = _ratio(repetition.time_in_target)
            declared_window = None if repetition.time_in_target is None else repetition.time_in_target.get("window")
            if coverage is None or coverage < .8 or target is None or declared_window != block.evaluation_window.value:
                missing.append(repetition.repetition_id)
            else:
                repetitions.append(target >= .7)
    if missing or not repetitions:
        return DimensionResult(result_id, AdherenceStatus.INSUFFICIENT_DATA,
            component.intensity.policy, missing_fields=tuple(missing or ("repetitions",)))
    recovery_missing = tuple(sorted(
        f"prescription_snapshot.{snapshot.prescription_snapshot_id}.components."
        f"{component.component_id}.blocks.{block.block_id}.recovery.evidence"
        for block in required
        if block.recovery.applicability is Applicability.REQUIRED
    ))
    if recovery_missing:
        return DimensionResult(
            result_id, AdherenceStatus.INSUFFICIENT_DATA, component.intensity.policy,
            missing_fields=recovery_missing,
            warnings=("required interval recovery target is not evaluable by the beta 0.4 policy",),
        )
    conformity = sum(repetitions) / len(repetitions)
    if conformity >= .9:
        status, band = AdherenceStatus.MET, SeverityBand.MAIN
    elif conformity >= .7:
        status, band = AdherenceStatus.PARTIALLY_MET, SeverityBand.SECONDARY
    else:
        status, band = AdherenceStatus.NOT_MET, SeverityBand.OUT_OF_BAND
    return DimensionResult(result_id, status, component.intensity.policy,
                           Direction.IN_LINE if status is AdherenceStatus.MET else Direction.UNDETERMINED,
                           band, {"conforming_repetitions": sum(repetitions), "required_repetitions": len(repetitions)})


def _intensity(component: PlannedComponent, observed: ObservedComponent,
               mapping, snapshot, session, result_id: str):
    if component.structure.session_type is SessionType.INTERVALS:
        return _interval_intensity(component, observed, mapping, snapshot, session, result_id)
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


def _identity(component, observed):
    if observed.discipline is None or observed.environment is None or observed.mode is None:
        return AdherenceStatus.INSUFFICIENT_DATA
    if (observed.discipline, observed.environment, observed.mode) == (
            component.discipline, component.environment, component.mode):
        return AdherenceStatus.MET
    allowed = any(s.discipline is observed.discipline and
                  (s.environment is None or s.environment is observed.environment) and
                  (s.mode is None or s.mode is observed.mode)
                  for s in component.allowed_substitutions)
    return AdherenceStatus.MET if allowed else AdherenceStatus.NOT_MET


def _observed_block_collection_is_incomplete(observed: ObservedComponent) -> bool:
    """Recognize only the canonical component-scoped block collection marker."""
    return any(field == "structure.blocks" for field in observed.missing_fields)


def _structure(component, observed, mapping, snapshot, session):
    block_collection_incomplete = _observed_block_collection_is_incomplete(observed)
    block_maps = [b for b in mapping.block_mappings if
                  (b.planned_block_ref and b.planned_block_ref.component_id == component.component_id) or
                  (b.observed_block_ref and b.observed_block_ref.component_id == observed.component_id)]
    planned_by_id = {b.block_id: b for b in component.structure.blocks}
    missing = [b for b in block_maps if b.match_status is MatchStatus.PLANNED_ONLY and
               b.planned_block_ref and planned_by_id[b.planned_block_ref.block_id].requiredness is Requiredness.REQUIRED]
    if missing and block_collection_incomplete:
        return AdherenceStatus.INSUFFICIENT_DATA
    if any(planned_by_id[b.planned_block_ref.block_id].block_type in (BlockType.MAIN_SET, BlockType.WORK) for b in missing):
        return AdherenceStatus.NOT_MET
    if missing:
        return AdherenceStatus.PARTIALLY_MET
    for block in component.structure.blocks:
        if block.requiredness is not Requiredness.REQUIRED or block.planned_repetitions is None:
            continue
        observed_block = _mapped_block(component, observed, block, mapping, snapshot, session)
        if observed_block is None:
            if block_collection_incomplete:
                return AdherenceStatus.INSUFFICIENT_DATA
            return AdherenceStatus.NOT_MET if block.block_type in (BlockType.MAIN_SET, BlockType.WORK) else AdherenceStatus.PARTIALLY_MET
        mapped_repetitions = [_mapped_repetition(component, observed, block, index,
            observed_block, mapping, snapshot, session)
            for index in range(block.planned_repetitions)]
        if any(item is None for item in mapped_repetitions):
            return AdherenceStatus.NOT_MET if block.block_type in (BlockType.MAIN_SET, BlockType.WORK) else AdherenceStatus.PARTIALLY_MET
        if [item.repetition_index for item in mapped_repetitions] != sorted(
                item.repetition_index for item in mapped_repetitions):
            return AdherenceStatus.PARTIALLY_MET
        if block.recovery.applicability is Applicability.REQUIRED:
            observed_recoveries = [candidate for candidate in observed.blocks
                                   if candidate.block_type is BlockType.RECOVERY]
            if observed_recoveries:
                # Beta 0.4 has no qualified RecoveryMapping/parent reference: even a
                # mapped or unique observed recovery cannot be associated implicitly.
                return AdherenceStatus.INSUFFICIENT_DATA
            return (AdherenceStatus.INSUFFICIENT_DATA
                    if block_collection_incomplete
                    else AdherenceStatus.NOT_MET)
    if snapshot.composition is Composition.BRICK:
        for transition in snapshot.transitions:
            planned_ref = PlannedTransitionRef(snapshot.prescription_snapshot_id, transition.transition_id)
            transition_maps = [item for item in mapping.transition_mappings if item.planned_transition_ref == planned_ref]
            if len(transition_maps) != 1 or transition_maps[0].match_status is not MatchStatus.MATCHED or transition_maps[0].observed_transition_ref is None:
                return AdherenceStatus.INSUFFICIENT_DATA
            observed_ref = transition_maps[0].observed_transition_ref
            matches = [item for item in session.transitions if
                       item.transition_id == observed_ref.transition_id and
                       observed_ref.session_id == session.session_id]
            component_map = {item.planned_component_ref.component_id: item.observed_component_ref.component_id
                for item in mapping.component_mappings if item.planned_component_ref and item.observed_component_ref}
            if (len(matches) != 1 or matches[0].duration_minutes is None or
                    matches[0].from_component_ref != component_map.get(transition.from_component_id) or
                    matches[0].to_component_ref != component_map.get(transition.to_component_id)):
                return AdherenceStatus.INSUFFICIENT_DATA
            if matches[0].duration_minutes > transition.applicable_limit_minutes:
                return AdherenceStatus.NOT_MET
    return AdherenceStatus.MET


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
        projection_errors = validate_source_conflict_projection(projection)
        if projection_errors:
            raise ValueError("; ".join(projection_errors))
        if (projection.actual_session_ref.session_id != session.session_id or
                conflict_ids.count(projection.source_conflict_id) != 1):
            raise ValueError("source-conflict projection is ghost or foreign-session")
    for impact in conflict_impacts:
        impact_errors = validate_source_conflict_impact(impact)
        if impact_errors:
            raise ValueError("; ".join(impact_errors))
        if (impact.prescription_mapping_ref != mapping.mapping_id or
                impact.source_conflict_ref.session_id != session.session_id or
                conflict_ids.count(impact.source_conflict_ref.conflict_id) != 1):
            raise ValueError("conflict impact is ghost, foreign-session, or cross-mapping")
        canonical = evaluate_source_conflict_impact(
            session, mapping, next(c for c in session.source_conflicts
                                   if c.get("conflict_id") == impact.source_conflict_ref.conflict_id),
            impact_evaluation_id=impact.conflict_impact_evaluation_id,
            evaluation_version=impact.evaluation_version, evaluated_at=impact.evaluated_at,
            provenance=impact.provenance)
        if impact != canonical:
            raise ValueError("conflict impact does not match canonical field-path classification")
    projection_conflicts = [p.source_conflict_id for p in conflict_projections]
    if len(projection_conflicts) != len(set(projection_conflicts)):
        raise ValueError("only one source-conflict projection per canonical conflict is allowed")
    impact_conflicts = [i.source_conflict_ref.conflict_id for i in conflict_impacts]
    if sorted(projection_conflicts) != sorted(conflict_ids) or sorted(impact_conflicts) != sorted(conflict_ids):
        raise ValueError("source conflicts require exact projection and impact coverage")
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
                identity = _identity(p, o)
                structure = _structure(p, o, mapping, snapshot, session)
                dimensions = [DimensionResult(f"{rid}:identity", identity, p.identity_policy),
                              _quantity(p, o, f"{rid}:quantity"), _intensity(p, o, mapping, snapshot, session, f"{rid}:intensity"),
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
    comp_status = (AdherenceStatus.INSUFFICIENT_DATA if session.composition is None else
                   AdherenceStatus.NOT_MET if session.composition is not snapshot.composition else
                   AdherenceStatus.NOT_MET if extras or missing else AdherenceStatus.MET)
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
