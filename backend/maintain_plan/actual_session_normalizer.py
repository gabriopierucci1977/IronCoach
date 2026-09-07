"""Pure normalization boundary for canonical observed MAINTAIN_PLAN sessions.

Callers explicitly associate observations before entering this module.  No
activity discovery, matching, prescription lookup, inference, clock or ID
generation is performed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from .models import (
    ActualSession, BlockType, CompletionObservation, Composition, Discipline,
    Environment, Mode, ObservedBlock, ObservedComponent, ObservedRepetition,
    ObservedTransition, SourceActivity,
)
from .validators import validate_actual_session


@dataclass(frozen=True)
class SourceActivityInput:
    source: str
    original_activity_id: str
    raw_ids: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RepetitionObservationInput:
    repetition_id: str
    repetition_index: int
    block_ref: str
    quantity_observation: Mapping[str, Any] | None = None
    intensity_observation: Mapping[str, Any] | None = None
    valid_coverage: Mapping[str, Any] | None = None
    time_in_target: Mapping[str, Any] | None = None
    source_segment_refs: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlockObservationInput:
    block_id: str
    block_index: int
    block_type: BlockType
    repetitions: tuple[RepetitionObservationInput, ...] = ()
    quantity_observation: Mapping[str, Any] | None = None
    intensity_observation: Mapping[str, Any] | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComponentObservationInput:
    component_id: str
    component_index: int
    discipline: Discipline | None
    source_activity_refs: tuple[str, ...]
    blocks: tuple[BlockObservationInput, ...] = ()
    environment: Environment | None = None
    mode: Mode | None = None
    source_segment_refs: tuple[str, ...] = ()
    start: datetime | None = None
    end: datetime | None = None
    quantity_primary_metric: str | None = None
    quantity_observation: Mapping[str, Any] | None = None
    quantity_unit: str | None = None
    secondary_metrics: tuple[Mapping[str, Any], ...] = ()
    intensity_methods: tuple[str, ...] = ()
    intensity_observations: Mapping[str, Any] | None = None
    temporal_coverage: Mapping[str, Any] | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    data_quality: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransitionObservationInput:
    transition_id: str
    from_component_ref: str
    to_component_ref: str
    start: datetime | None = None
    end: datetime | None = None
    duration_minutes: int | float | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActualSessionInput:
    session_id: str
    source_activities: tuple[SourceActivityInput, ...]
    start: datetime
    end: datetime | None
    timezone: str
    composition: Composition | None
    components: tuple[ComponentObservationInput, ...]
    normalized_at: datetime
    transitions: tuple[TransitionObservationInput, ...] = ()
    completion_status: str | None = None
    interruption_reason: str | None = None
    safety_interruption: bool | None = None
    athlete_feedback: Mapping[str, Any] | None = None
    weather_context: tuple[Mapping[str, Any], ...] = ()
    source_conflicts: tuple[Mapping[str, Any], ...] = ()
    data_quality: Mapping[str, Any] = field(default_factory=dict)
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class ActualSessionNormalizer:
    """Copy explicit observations into a validated, deeply frozen session."""

    @staticmethod
    def normalize(value: ActualSessionInput) -> ActualSession:
        if not isinstance(value, ActualSessionInput):
            raise TypeError("normalize requires ActualSessionInput")

        components = tuple(
            ObservedComponent(
                component_id=item.component_id,
                component_index=item.component_index,
                discipline=item.discipline,
                blocks=tuple(
                    ObservedBlock(
                        block_id=block.block_id,
                        block_index=block.block_index,
                        repetitions=tuple(
                            ObservedRepetition(**vars(repetition))
                            for repetition in block.repetitions
                        ),
                        block_type=block.block_type,
                        quantity_observation=block.quantity_observation,
                        intensity_observation=block.intensity_observation,
                        provenance=block.provenance,
                        missing_fields=block.missing_fields,
                        warnings=block.warnings,
                    ) for block in item.blocks
                ),
                quantity_observation=item.quantity_observation,
                environment=item.environment,
                mode=item.mode,
                source_activity_refs=item.source_activity_refs,
                source_segment_refs=item.source_segment_refs,
                start=item.start,
                end=item.end,
                quantity_primary_metric=item.quantity_primary_metric,
                quantity_unit=item.quantity_unit,
                secondary_metrics=item.secondary_metrics,
                intensity_methods=item.intensity_methods,
                intensity_observations=item.intensity_observations,
                temporal_coverage=item.temporal_coverage,
                provenance=item.provenance,
                missing_fields=item.missing_fields,
                warnings=item.warnings,
                data_quality=item.data_quality,
            ) for item in value.components
        )
        transitions = tuple(ObservedTransition(**vars(item)) for item in value.transitions)
        session = ActualSession(
            session_id=value.session_id,
            start=value.start,
            composition=value.composition,
            components=components,
            transition_ids=tuple(item.transition_id for item in transitions),
            source_activities=tuple(SourceActivity(**vars(item)) for item in value.source_activities),
            end=value.end,
            timezone=value.timezone,
            transitions=transitions,
            completion=CompletionObservation(value.completion_status,
                                             value.interruption_reason,
                                             value.safety_interruption),
            athlete_feedback=value.athlete_feedback,
            weather_context=value.weather_context,
            source_conflicts=value.source_conflicts,
            data_quality=value.data_quality,
            provenance={"normalized_at": value.normalized_at},
            missing_fields=value.missing_fields,
            warnings=value.warnings,
        )
        errors = validate_actual_session(session)
        if errors:
            raise ValueError("; ".join(errors))
        return session
